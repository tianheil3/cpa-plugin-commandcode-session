package main

import (
	"context"
	"strings"
	"testing"
	"time"

	"github.com/router-for-me/CLIProxyAPI/v7/sdk/pluginapi"
)

func TestStableCompatAuthIDIsDeterministic(t *testing.T) {
	t.Parallel()
	a := stableCompatAuthID("commandcode", "sk-one", "https://api.commandcode.ai/provider/v1", "direct")
	b := stableCompatAuthID("commandcode", "sk-one", "https://api.commandcode.ai/provider/v1", "direct")
	c := stableCompatAuthID("commandcode", "sk-two", "https://api.commandcode.ai/provider/v1", "direct")
	if a == "" || a != b {
		t.Fatalf("a=%q b=%q", a, b)
	}
	if a == c {
		t.Fatal("different keys must not share auth id")
	}
	if len(a) < len("openai-compatibility:commandcode:")+12 {
		t.Fatalf("id too short: %q", a)
	}
}

func TestHandleRegisterAdvertisesScheduler(t *testing.T) {
	raw, err := handleRegister([]byte(`{"config_yaml":null}`))
	if err != nil {
		t.Fatal(err)
	}
	text := string(raw)
	if !strings.Contains(text, `"scheduler":true`) {
		t.Fatalf("register payload missing scheduler: %s", text)
	}
}

func TestPickFallsThroughOnMixedPool(t *testing.T) {
	t.Parallel()
	p := &sessionPlugin{cfg: defaultConfig()}
	resp, err := p.Pick(context.Background(), pluginapi.SchedulerPickRequest{
		Provider: "openai-compatibility",
		Candidates: []pluginapi.SchedulerAuthCandidate{
			{ID: "openai-compatibility:commandcode:aaaaaaaaaaaa", Provider: "openai-compatible-commandcode", Attributes: map[string]string{"compat_name": "commandcode"}},
			{ID: "openai-compatibility:openrouter:bbbbbbbbbbbb", Provider: "openai-compatible-openrouter", Attributes: map[string]string{"compat_name": "openrouter"}},
		},
	})
	if err != nil {
		t.Fatal(err)
	}
	if resp.Handled {
		t.Fatalf("mixed pool must fall through: %#v", resp)
	}
}

func TestPickIgnoresOtherProviders(t *testing.T) {
	t.Parallel()
	p := &sessionPlugin{cfg: defaultConfig()}
	resp, err := p.Pick(context.Background(), pluginapi.SchedulerPickRequest{
		Provider: "codex",
		Candidates: []pluginapi.SchedulerAuthCandidate{{
			ID:       "codex-1",
			Provider: "codex",
		}},
	})
	if err != nil {
		t.Fatal(err)
	}
	if resp.Handled {
		t.Fatalf("codex must fall through: %#v", resp)
	}
}

func TestPickPrefersHigherRollingQuota(t *testing.T) {
	t.Parallel()
	low := "openai-compatibility:commandcode:lowlowlowlow"
	high := "openai-compatibility:commandcode:highhighhigh"
	p := &sessionPlugin{cfg: defaultConfig()}
	p.rememberUsage(low, "sk-LOW…low1", zenUsage{Rolling: zenUsageWindow{Percent: 90}})
	p.rememberUsage(high, "sk-HI…high", zenUsage{Rolling: zenUsageWindow{Percent: 10}})
	resp, err := p.Pick(context.Background(), pluginapi.SchedulerPickRequest{
		Provider: "openai-compatible-commandcode",
		Candidates: []pluginapi.SchedulerAuthCandidate{
			{ID: low, Provider: "openai-compatible-commandcode", Attributes: map[string]string{"compat_name": "commandcode"}},
			{ID: high, Provider: "openai-compatible-commandcode", Attributes: map[string]string{"compat_name": "commandcode"}},
		},
	})
	if err != nil {
		t.Fatal(err)
	}
	if !resp.Handled || resp.AuthID != high {
		t.Fatalf("resp = %#v want %s", resp, high)
	}
}

func TestPickSkipsRecentlyExhaustedKey(t *testing.T) {
	t.Parallel()
	dead := "openai-compatibility:commandcode:deaddeaddead"
	live := "openai-compatibility:commandcode:livelivelive"
	p := &sessionPlugin{cfg: defaultConfig()}
	p.rememberUsage(dead, "sk-DEAD…dead", zenUsage{Rolling: zenUsageWindow{Percent: 5}})
	p.rememberUsage(live, "sk-LIVE…live", zenUsage{Rolling: zenUsageWindow{Percent: 40}})
	p.markExhausted(dead, time.Now().Add(time.Hour))
	resp, err := p.Pick(context.Background(), pluginapi.SchedulerPickRequest{
		Provider: "openai-compatible-commandcode",
		Candidates: []pluginapi.SchedulerAuthCandidate{
			{ID: dead, Provider: "openai-compatible-commandcode", Attributes: map[string]string{"compat_name": "commandcode", "base_url": "https://api.commandcode.ai/provider/v1"}},
			{ID: live, Provider: "openai-compatible-commandcode", Attributes: map[string]string{"compat_name": "commandcode", "base_url": "https://api.commandcode.ai/provider/v1"}},
		},
	})
	if err != nil {
		t.Fatal(err)
	}
	if !resp.Handled || resp.AuthID != live {
		t.Fatalf("resp = %#v want %s", resp, live)
	}
}

func TestHandleUsageMarksQuotaExhausted(t *testing.T) {
	t.Parallel()
	p := &sessionPlugin{cfg: defaultConfig()}
	id := "openai-compatibility:commandcode:abcabcabcabc"
	p.rememberUsage(id, "sk-ABC…abc1", zenUsage{Rolling: zenUsageWindow{Percent: 10}})
	p.HandleUsage(context.Background(), pluginapi.UsageRecord{
		Provider: "openai-compatible-commandcode",
		BaseURL:  "https://api.commandcode.ai/provider/v1",
		AuthID:   id,
		Failed:   true,
		Failure:  pluginapi.UsageFailure{StatusCode: 429, Body: "rate limit"},
	})
	p.mu.Lock()
	until := p.quotaByAuthID[id].ExhaustedUntil
	p.mu.Unlock()
	if until.IsZero() || until.Before(time.Now()) {
		t.Fatalf("exhausted until = %v", until)
	}
}

package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"strconv"
	"strings"
	"time"

	"gopkg.in/yaml.v3"
)

type zenUsageWindow struct {
	Status   string  `json:"status"`
	Percent  float64 `json:"percent"`
	ResetsAt string  `json:"resetsAt"`
}

type zenUsage struct {
	Rolling zenUsageWindow `json:"rolling"`
	Weekly  zenUsageWindow `json:"weekly"`
	Monthly zenUsageWindow `json:"monthly"`
	Plan    string         `json:"plan,omitempty"`
}

type zenUsageResponse struct {
	Usage zenUsage `json:"usage"`
}

func remainingFraction(usedPercent float64) float64 {
	frac := 1 - usedPercent/100
	if frac < 0 {
		return 0
	}
	if frac > 1 {
		return 1
	}
	return frac
}

func alphaBaseFromProvider(providerBase string) string {
	base := strings.TrimRight(strings.TrimSpace(providerBase), "/")
	base = strings.TrimSuffix(base, "/provider/v1")
	base = strings.TrimSuffix(base, "/v1")
	if base == "" {
		return defaultAlphaBaseURL
	}
	return base
}

func outboundClient(cpaConfigPath string, timeout time.Duration) *http.Client {
	if timeout <= 0 {
		timeout = 25 * time.Second
	}
	transport, ok := http.DefaultTransport.(*http.Transport)
	if !ok || transport == nil {
		return &http.Client{Timeout: timeout}
	}
	cloned := transport.Clone()
	proxyURL := readCPAProxyURL(cpaConfigPath)
	switch strings.ToLower(strings.TrimSpace(proxyURL)) {
	case "", "env":
		// keep DefaultTransport proxy (environment)
	case "direct", "none":
		cloned.Proxy = nil
	default:
		if parsed, err := url.Parse(proxyURL); err == nil && parsed.Scheme != "" {
			cloned.Proxy = http.ProxyURL(parsed)
		}
	}
	return &http.Client{Timeout: timeout, Transport: cloned}
}

func readCPAProxyURL(configPath string) string {
	raw, err := os.ReadFile(resolveConfigPath(configPath))
	if err != nil {
		return ""
	}
	var root yaml.Node
	if yaml.Unmarshal(raw, &root) != nil {
		return ""
	}
	doc := mappingNode(&root)
	return strings.TrimSpace(mappingGetString(doc, "proxy-url"))
}

func zenGet(ctx context.Context, requestURL, apiKey, cpaConfigPath string) ([]byte, int, error) {
	if ctx == nil {
		ctx = context.Background()
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, requestURL, nil)
	if err != nil {
		return nil, 0, err
	}
	req.Header.Set("Authorization", "Bearer "+strings.TrimSpace(apiKey))
	req.Header.Set("Accept", "application/json")
	req.Header.Set("User-Agent", "cpa-plugin-commandcode-session/"+pluginVersion)
	client := outboundClient(cpaConfigPath, 25*time.Second)
	resp, err := client.Do(req)
	if err != nil {
		return nil, 0, err
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(io.LimitReader(resp.Body, 2<<20))
	if err != nil {
		return nil, resp.StatusCode, err
	}
	return body, resp.StatusCode, nil
}

func fetchZenUsage(ctx context.Context, providerBaseURL, apiKey string) (zenUsage, error) {
	return fetchZenUsageAt(ctx, providerBaseURL, apiKey, "config.yaml")
}

func fetchZenUsageAt(ctx context.Context, providerBaseURL, apiKey, cpaConfigPath string) (zenUsage, error) {
	creditsURL := alphaBaseFromProvider(providerBaseURL) + "/alpha/billing/credits"
	raw, status, err := zenGet(ctx, creditsURL, apiKey, cpaConfigPath)
	if err == nil && status < 400 {
		if usage, parseErr := parseCreditsUsage(raw); parseErr == nil {
			return usage, nil
		}
	}
	usageURL := strings.TrimRight(providerBaseURL, "/") + "/usage"
	raw, status, err = zenGet(ctx, usageURL, apiKey, cpaConfigPath)
	if err != nil {
		return zenUsage{}, err
	}
	if status >= 400 {
		return zenUsage{}, fmt.Errorf("usage HTTP %d: %s", status, summarizeBody(raw))
	}
	if usage, parseErr := parseCreditsUsage(raw); parseErr == nil {
		return usage, nil
	}
	var parsed zenUsageResponse
	if err := json.Unmarshal(raw, &parsed); err != nil {
		return zenUsage{}, err
	}
	return parsed.Usage, nil
}

func fetchZenModels(ctx context.Context, baseURL, apiKey string) ([]string, error) {
	return fetchZenModelsAt(ctx, baseURL, apiKey, "config.yaml")
}

func fetchZenModelsAt(ctx context.Context, baseURL, apiKey, cpaConfigPath string) ([]string, error) {
	raw, status, err := zenGet(ctx, strings.TrimRight(baseURL, "/")+"/models", apiKey, cpaConfigPath)
	if err != nil {
		return nil, err
	}
	if status >= 400 {
		return nil, fmt.Errorf("models HTTP %d: %s", status, summarizeBody(raw))
	}
	return parseZenModelIDs(raw)
}

func parseZenModelIDs(raw []byte) ([]string, error) {
	var payload map[string]any
	if err := json.Unmarshal(raw, &payload); err != nil {
		return nil, err
	}
	items, _ := payload["data"].([]any)
	if items == nil {
		if nested, ok := payload["models"].([]any); ok {
			items = nested
		}
	}
	out := make([]string, 0, len(items))
	seen := map[string]struct{}{}
	for _, item := range items {
		obj, ok := item.(map[string]any)
		if !ok {
			continue
		}
		if !supportsChatCompletions(obj["supported_endpoints"]) {
			continue
		}
		id, _ := obj["id"].(string)
		if id == "" {
			id, _ = obj["name"].(string)
		}
		id = strings.TrimSpace(id)
		id = strings.TrimPrefix(id, "commandcode/")
		if id == "" {
			continue
		}
		if _, exists := seen[id]; exists {
			continue
		}
		seen[id] = struct{}{}
		out = append(out, id)
	}
	if len(out) == 0 {
		return nil, fmt.Errorf("upstream returned no chat-completions models")
	}
	return out, nil
}

func supportsChatCompletions(raw any) bool {
	switch v := raw.(type) {
	case nil:
		return true
	case []any:
		if len(v) == 0 {
			return true
		}
		for _, item := range v {
			s, _ := item.(string)
			if strings.Contains(strings.ToLower(s), "chat/completions") {
				return true
			}
		}
		return false
	default:
		return true
	}
}

func parseCreditsUsage(raw []byte) (zenUsage, error) {
	var payload map[string]any
	if err := json.Unmarshal(raw, &payload); err != nil {
		return zenUsage{}, err
	}
	if data, ok := payload["data"].(map[string]any); ok {
		if _, hasCredits := payload["credits"]; !hasCredits {
			payload = data
		}
		if _, hasWindows := payload["windowLimits"]; !hasWindows && data["windowLimits"] != nil {
			payload = data
		}
	}
	credits, _ := payload["credits"].(map[string]any)
	windows, _ := payload["windowLimits"].(map[string]any)
	if windows == nil {
		windows, _ = payload["window_limits"].(map[string]any)
	}
	if credits == nil && windows == nil {
		return zenUsage{}, fmt.Errorf("credits payload missing windowLimits")
	}
	plan := anyString(credits, "planId", "plan_id", "plan")
	usage := zenUsage{
		Rolling: windowFromMap(pickWindow(windows, "fiveHour", "five_hour", "rolling5h", "5h")),
		Weekly:  windowFromMap(pickWindow(windows, "weekly", "week", "7d")),
		Plan:    plan,
	}
	remaining := anyFloat(credits, "monthlyCredits", "monthly_credits")
	cap := planMonthlyCap(plan)
	usage.Monthly = monthlyWindow(remaining, cap)
	return usage, nil
}

func pickWindow(windows map[string]any, names ...string) map[string]any {
	if windows == nil {
		return nil
	}
	for _, name := range names {
		if item, ok := windows[name].(map[string]any); ok {
			return item
		}
	}
	return nil
}

func windowFromMap(raw map[string]any) zenUsageWindow {
	if raw == nil {
		return zenUsageWindow{Status: "unknown"}
	}
	used := anyFloat(raw, "used", "usage", "usedCredits", "used_credits")
	cap := anyFloat(raw, "cap", "limit", "max")
	percent := 0.0
	if cap > 0 {
		percent = used / cap * 100
	}
	if percent < 0 {
		percent = 0
	}
	if percent > 100 {
		percent = 100
	}
	status := "ok"
	if anyBool(raw, "exceeded") || percent >= 100 {
		status = "exceeded"
	}
	return zenUsageWindow{
		Status:   status,
		Percent:  percent,
		ResetsAt: formatResetAt(raw["resetAt"], raw["reset_at"], raw["resetsAt"]),
	}
}

func monthlyWindow(remaining, cap float64) zenUsageWindow {
	if cap <= 0 {
		status := "ok"
		percent := 0.0
		if remaining <= 0 {
			status = "unknown"
			percent = 0
		}
		return zenUsageWindow{Status: status, Percent: percent}
	}
	used := cap - remaining
	if used < 0 {
		used = 0
	}
	percent := used / cap * 100
	if percent > 100 {
		percent = 100
	}
	status := "ok"
	if remaining <= 0 {
		status = "exceeded"
		percent = 100
	}
	return zenUsageWindow{Status: status, Percent: percent}
}

func planMonthlyCap(plan string) float64 {
	switch strings.ToLower(strings.TrimSpace(plan)) {
	case "go":
		return 10
	case "goat":
		return 70
	case "pro":
		return 80
	case "max", "max10", "max_10", "max10x", "max_10x":
		return 150
	case "max20", "max_20", "max20x", "max_20x":
		return 300
	case "team", "team_pro", "team-pro":
		return 40
	default:
		return 0
	}
}

func formatResetAt(values ...any) string {
	for _, value := range values {
		switch v := value.(type) {
		case string:
			if s := strings.TrimSpace(v); s != "" {
				if ms, err := strconv.ParseFloat(s, 64); err == nil && ms > 1e11 {
					return time.UnixMilli(int64(ms)).UTC().Format(time.RFC3339)
				}
				return s
			}
		case float64:
			if v > 1e11 {
				return time.UnixMilli(int64(v)).UTC().Format(time.RFC3339)
			}
			if v > 1e9 {
				return time.Unix(int64(v), 0).UTC().Format(time.RFC3339)
			}
		case json.Number:
			if f, err := v.Float64(); err == nil {
				return formatResetAt(f)
			}
		}
	}
	return ""
}

func anyString(m map[string]any, keys ...string) string {
	if m == nil {
		return ""
	}
	for _, key := range keys {
		switch v := m[key].(type) {
		case string:
			if s := strings.TrimSpace(v); s != "" {
				return s
			}
		}
	}
	return ""
}

func anyFloat(m map[string]any, keys ...string) float64 {
	if m == nil {
		return 0
	}
	for _, key := range keys {
		switch v := m[key].(type) {
		case float64:
			return v
		case json.Number:
			f, _ := v.Float64()
			return f
		case string:
			f, _ := strconv.ParseFloat(strings.TrimSpace(v), 64)
			return f
		}
	}
	return 0
}

func anyBool(m map[string]any, keys ...string) bool {
	if m == nil {
		return false
	}
	for _, key := range keys {
		switch v := m[key].(type) {
		case bool:
			return v
		case string:
			return strings.EqualFold(strings.TrimSpace(v), "true")
		}
	}
	return false
}

func summarizeBody(raw []byte) string {
	s := strings.TrimSpace(string(raw))
	if len(s) > 240 {
		return s[:240]
	}
	return s
}

func maskKey(key string) string {
	key = strings.TrimSpace(key)
	if len(key) <= 10 {
		return "user_***"
	}
	return key[:6] + "…" + key[len(key)-4:]
}

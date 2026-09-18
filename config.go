package main

import (
	"strings"

	"gopkg.in/yaml.v3"
)

type pluginConfig struct {
	RewriteBody    bool     `yaml:"rewrite_body"`
	ClampReasoning bool     `yaml:"clamp_reasoning"`
	DropJSONSchema bool     `yaml:"drop_json_schema"`
	FunctionTools  bool     `yaml:"function_tools"`
	MatchModels    []string `yaml:"match_models"`
	MatchPrefixes  []string `yaml:"match_prefixes"`
	SkipModels     []string `yaml:"skip_models"`
	CPAConfigPath  string   `yaml:"cpa_config_path"`
	ProviderName   string   `yaml:"provider_name"`
	BaseURL        string   `yaml:"base_url"`
	AlphaBaseURL   string   `yaml:"alpha_base_url"`
	ProxyURL       string   `yaml:"proxy_url"`
	AliasPrefix    string   `yaml:"alias_prefix"`
	ZDR            bool     `yaml:"zdr"`
	IncludeClaude  bool     `yaml:"include_claude"`
}

func defaultConfig() pluginConfig {
	return pluginConfig{
		RewriteBody:    true,
		ClampReasoning: true,
		DropJSONSchema: true,
		FunctionTools:  true,
		CPAConfigPath:  "config.yaml",
		ProviderName:   "commandcode",
		BaseURL:        defaultZenBaseURL,
		AliasPrefix:    "commandcode",
	}
}

func parseConfig(raw []byte) (pluginConfig, error) {
	cfg := defaultConfig()
	if len(raw) == 0 {
		return cfg, nil
	}
	if err := yaml.Unmarshal(raw, &cfg); err != nil {
		return pluginConfig{}, err
	}
	if strings.TrimSpace(cfg.CPAConfigPath) == "" {
		cfg.CPAConfigPath = "config.yaml"
	}
	if strings.TrimSpace(cfg.ProviderName) == "" {
		cfg.ProviderName = "commandcode"
	}
	if strings.TrimSpace(cfg.BaseURL) == "" {
		cfg.BaseURL = defaultZenBaseURL
	}
	if strings.TrimSpace(cfg.AlphaBaseURL) == "" {
		cfg.AlphaBaseURL = defaultAlphaBaseURL
	}
	if strings.TrimSpace(cfg.AliasPrefix) == "" {
		cfg.AliasPrefix = "commandcode"
	}
	return cfg, nil
}

func (c pluginConfig) aliasPrefix() string {
	prefix := strings.TrimSpace(c.AliasPrefix)
	if prefix == "" {
		return "commandcode"
	}
	return strings.Trim(prefix, "/")
}

func (c pluginConfig) modelAlias(name string) string {
	name = strings.TrimSpace(name)
	prefix := c.aliasPrefix() + "/"
	if name == "" {
		return ""
	}
	if strings.HasPrefix(name, prefix) {
		return name
	}
	return prefix + name
}

func (c pluginConfig) providerName() string {
	name := strings.TrimSpace(c.ProviderName)
	if name == "" {
		return "commandcode"
	}
	return name
}

func (c pluginConfig) zenBaseURL() string {
	base := strings.TrimSpace(c.BaseURL)
	if base == "" {
		return defaultZenBaseURL
	}
	return strings.TrimRight(base, "/")
}

func (c pluginConfig) alphaBaseURL() string {
	base := strings.TrimSpace(c.AlphaBaseURL)
	if base == "" {
		return alphaBaseFromProvider(c.zenBaseURL())
	}
	return strings.TrimRight(base, "/")
}

func (c pluginConfig) shouldRewrite(model, requested string) bool {
	if !c.RewriteBody {
		return false
	}
	slug := strings.TrimSpace(model)
	if slug == "" {
		slug = strings.TrimSpace(requested)
	}
	lower := strings.ToLower(slug)
	for _, skip := range c.SkipModels {
		if strings.EqualFold(slug, skip) {
			return false
		}
	}
	if len(c.MatchModels) == 0 && len(c.MatchPrefixes) == 0 {
		return true
	}
	for _, name := range c.MatchModels {
		if strings.EqualFold(slug, name) {
			return true
		}
	}
	for _, prefix := range c.MatchPrefixes {
		if prefix != "" && strings.HasPrefix(lower, strings.ToLower(prefix)) {
			return true
		}
	}
	return false
}

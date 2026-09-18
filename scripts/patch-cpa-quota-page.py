#!/usr/bin/env python3
"""Add Command Code to a management.html that already has the OpenCode Go patch.

Requires:

    remote-management.disable-auto-update-panel: true

Apply OpenCode Go's patch first. This script extends those hooks so both
providers show on 配额管理 and 认证文件, with models + quota.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

TOKEN_MARK = "data-commandcode-token-panel"
TOKEN_SCRIPT = """  <script data-commandcode-token-panel="1">
(function(){if(window.__cpaCcTokens)return;window.__cpaCcTokens=1;var cache=null,fetched=0,timer=null;function key(){try{if(window.__CPA_MGMT_KEY)return String(window.__CPA_MGMT_KEY)}catch(e){}try{return sessionStorage.getItem("cpa:managementKey")||""}catch(e){}return ""}function fmt(n){n=Number(n)||0;if(n>=1e8)return(n/1e8).toFixed(2)+" 亿";if(n>=1e4)return(n/1e4).toFixed(2)+" 万";return String(Math.round(n))}function rate(t){if(t&&t.cache_hit_display)return t.cache_hit_display;var i=Number(t&&t.input_tokens||0),c=Number(t&&t.cache_read_tokens||0);if(c>i)i=i+c+Number(t&&t.cache_write_tokens||0);if(i<=0)return"—";return(Math.min(100,c/i*100)).toFixed(1)+"%"}function box(t){if(!t)return"";var sig=String((t.total_tokens||0)+":"+(t.requests||0)+":"+(t.updated_at||""));return '<div data-commandcode-token-box="1" data-sig="'+sig+'" style="margin:12px 0 16px;padding:12px 14px;border:1px solid var(--border-color,#d5d2cb);border-radius:12px;background:var(--bg-secondary,#faf9f5);font-size:13px;line-height:1.55"><div style="font-weight:700;margin-bottom:6px">本机累计 Token（Command Code）</div><div>合计 <b>'+fmt(t.total_tokens)+'</b> · 输入 '+fmt(t.input_tokens)+' · 输出 '+fmt(t.output_tokens)+(t.reasoning_tokens?(" · 推理 "+fmt(t.reasoning_tokens)):"")+'</div><div>缓存读取 '+fmt(t.cache_read_tokens)+' · 缓存写入 '+fmt(t.cache_write_tokens)+' · 命中率 <b>'+rate(t)+'</b> · 成功请求 '+(t.requests||0)+'</div><div style="opacity:.72;margin-top:4px">从本机插件记账，不是官方账单。官方额度窗口仍是剩余百分比。</div></div>'}async function load(){var k=key();if(!k)return null;try{var r=await fetch("/v0/management/plugins/commandcode-session/status",{headers:{Authorization:"Bearer "+k,"X-Management-Key":k},credentials:"same-origin"});if(!r.ok)return null;var d=await r.json();return d&&d.tokens||null}catch(e){return null}}function findHost(){var nodes=document.querySelectorAll("h1,h2,h3,h4");for(var i=0;i<nodes.length;i++){var t=(nodes[i].textContent||"").trim();if(/Command Code/.test(t)&&(/额度|配額|Quota|Квота/.test(t)))return nodes[i]}return null}async function paint(){if(!/#\\/?quota/i.test(location.hash||"")){var old=document.querySelector("[data-commandcode-token-box]");if(old)old.remove();return}var host=findHost();if(!host)return;var now=Date.now();if(!cache||now-fetched>8000){fetched=now;cache=await load()}if(!cache)return;var html=box(cache);var prev=document.querySelector("[data-commandcode-token-box]");var sig=String((cache.total_tokens||0)+":"+(cache.requests||0)+":"+(cache.updated_at||""));if(prev&&prev.getAttribute("data-sig")===sig)return;if(prev){prev.outerHTML=html;return}var wrap=document.createElement("div");wrap.innerHTML=html;host.parentNode.insertBefore(wrap.firstChild,host.nextSibling)}function schedule(){clearTimeout(timer);timer=setTimeout(paint,250)}addEventListener("hashchange",schedule);var mo=new MutationObserver(schedule);mo.observe(document.documentElement,{childList:true,subtree:true});schedule();})();
</script>
"""

AUTH_LIST_OLD = (
    "Oy={list:async()=>{let e=await op.get(`/auth-files`);try{let t=await op.get(`/plugins/opencode-session/auth-files`),n=t?.files||[];"
    "if(Array.isArray(n)&&n.length){try{let r=await op.get(`/openai-compatibility`),"
    "a=(r?.[`openai-compatibility`]||[]).find(s=>String(s?.name||``).trim().toLowerCase()===`opencode-go`),"
    "c=a?.[`api-key-entries`]||[];n.forEach((f,i)=>{let x=c[i]?.[`auth-index`]??c[i]?.authIndex??c[i]?.auth_index;"
    "if(x){f.auth_index=String(x);f.authIndex=String(x)}})}catch(e){}"
    "let s=new Set((e?.files||[]).map(f=>String(f?.id||``)));"
    "e={...e,files:[...e?.files||[],...n.filter(f=>!s.has(String(f?.id||``)))]}}}catch(e){}return xy(e)}"
)
AUTH_LIST_NEW = (
    "Oy={list:async()=>{let e=await op.get(`/auth-files`);"
    "async function k(p,q){try{let t=await op.get(`/plugins/${p}/auth-files`),n=t?.files||[];"
    "if(Array.isArray(n)&&n.length){try{let r=await op.get(`/openai-compatibility`),"
    "a=(r?.[`openai-compatibility`]||[]).find(s=>String(s?.name||``).trim().toLowerCase()===q),"
    "c=a?.[`api-key-entries`]||[];n.forEach((f,i)=>{let x=c[i]?.[`auth-index`]??c[i]?.authIndex??c[i]?.auth_index;"
    "if(x){f.auth_index=String(x);f.authIndex=String(x)}})}catch(e){}"
    "let s=new Set((e?.files||[]).map(f=>String(f?.id||``)));"
    "e={...e,files:[...e?.files||[],...n.filter(f=>!s.has(String(f?.id||``)))]}}}catch(e){}}"
    "await k(`opencode-session`,`opencode-go`);await k(`commandcode-session`,`commandcode`);return xy(e)}"
)

GET_MODELS_OLD = (
    "async getModelsForAuthFile(e){try{let t=await op.get(`/auth-files/models?name=${encodeURIComponent(e)}`),"
    "n=t.models??t.models;if(Array.isArray(n)&&n.length)return n}catch(e){}"
    "try{let r=await op.get(`/plugins/opencode-session/auth-files`),"
    "a=(r?.files||[]).find(t=>t.name===e||t.id===e);"
    "if(Array.isArray(a?.models)&&a.models.length)return a.models.map(t=>typeof t==`string`?{id:t}:t)}"
    "catch(e){}return[]}"
)
GET_MODELS_NEW = (
    "async getModelsForAuthFile(e){try{let t=await op.get(`/auth-files/models?name=${encodeURIComponent(e)}`),"
    "n=t.models??t.models;if(Array.isArray(n)&&n.length)return n}catch(e){}"
    "for(let p of[`opencode-session`,`commandcode-session`]){"
    "try{let r=await op.get(`/plugins/${p}/auth-files`),"
    "a=(r?.files||[]).find(t=>t.name===e||t.id===e);"
    "if(Array.isArray(a?.models)&&a.models.length)return a.models.map(t=>typeof t==`string`?{id:t}:t)}"
    "catch(e){}}return[]}"
)

SET_STATUS_OLD = (
    "setStatus:async(e,t)=>String(e||``).startsWith(`opencode-go-`)||String(e||``).includes(`openai-compatibility:opencode-go:`)"
    "?op.patch(`/plugins/opencode-session/auth-files/status`,{name:e,disabled:t})"
    ":op.patch(`/auth-files/status`,{name:e,disabled:t})"
)
SET_STATUS_NEW = (
    "setStatus:async(e,t)=>{let n=String(e||``);"
    "if(n.startsWith(`opencode-go-`)||n.includes(`openai-compatibility:opencode-go:`))"
    "return op.patch(`/plugins/opencode-session/auth-files/status`,{name:e,disabled:t});"
    "if(n.startsWith(`commandcode-`)||n.includes(`openai-compatibility:commandcode:`))"
    "return op.patch(`/plugins/commandcode-session/auth-files/status`,{name:e,disabled:t});"
    "return op.patch(`/auth-files/status`,{name:e,disabled:t})}"
)

DELETE_FILES_OLD = (
    "deleteFiles:async e=>{let t=iy(e);if(t.length===0)return{status:`ok`,deleted:0,files:[],failed:[]};"
    "let n=t.filter(e=>String(e||``).startsWith(`opencode-go-`)||String(e||``).includes(`openai-compatibility:opencode-go:`)),"
    "r=t.filter(e=>!(String(e||``).startsWith(`opencode-go-`)||String(e||``).includes(`openai-compatibility:opencode-go:`))),"
    "i={deleted:0,files:[],failed:[]};"
    "if(n.length){let a=cy(await op.delete(`/plugins/opencode-session/auth-files`,{data:{names:n}}),n);"
    "i.deleted+=a.deleted??0;i.files.push(...a.files||[]);i.failed.push(...a.failed||[])}"
    "if(r.length){let a=cy(await op.delete(`/auth-files`,{data:{names:r}}),r);"
    "i.deleted+=a.deleted??0;i.files.push(...a.files||[]);i.failed.push(...a.failed||[])}"
    "return{status:i.failed.length?`partial`:`ok`,deleted:i.deleted,files:i.files,failed:i.failed}}"
)
DELETE_FILES_NEW = (
    "deleteFiles:async e=>{let t=iy(e);if(t.length===0)return{status:`ok`,deleted:0,files:[],failed:[]};"
    "let oc=e=>String(e||``).startsWith(`opencode-go-`)||String(e||``).includes(`openai-compatibility:opencode-go:`),"
    "cc=e=>String(e||``).startsWith(`commandcode-`)||String(e||``).includes(`openai-compatibility:commandcode:`),"
    "n=t.filter(oc),q=t.filter(cc),r=t.filter(e=>!oc(e)&&!cc(e)),i={deleted:0,files:[],failed:[]};"
    "if(n.length){let a=cy(await op.delete(`/plugins/opencode-session/auth-files`,{data:{names:n}}),n);"
    "i.deleted+=a.deleted??0;i.files.push(...a.files||[]);i.failed.push(...a.failed||[])}"
    "if(q.length){let a=cy(await op.delete(`/plugins/commandcode-session/auth-files`,{data:{names:q}}),q);"
    "i.deleted+=a.deleted??0;i.files.push(...a.files||[]);i.failed.push(...a.failed||[])}"
    "if(r.length){let a=cy(await op.delete(`/auth-files`,{data:{names:r}}),r);"
    "i.deleted+=a.deleted??0;i.files.push(...a.files||[]);i.failed.push(...a.failed||[])}"
    "return{status:i.failed.length?`partial`:`ok`,deleted:i.deleted,files:i.files,failed:i.failed}}"
)

CC_ADAPTER = (
    '["commandcode"]:{type:`commandcode`,i18nPrefix:`commandcode_quota`,'
    "filterFn:e=>{let t=n_(e);return t===`commandcode`||t===`openai-compatible-commandcode`"
    "||t===`openai-compatibility:commandcode`||t.endsWith(`-commandcode`)||t.endsWith(`:commandcode`)},"
    "fetchQuota:async(e,t)=>{let n=bg(e.auth_index??e.authIndex),r=null;"
    "if(n)try{r=await op.post(`/quota/fetch`,{auth_index:n})}catch(e){}"
    "if(!(r&&Array.isArray(r.groups))){let a=await op.get(`/plugins/commandcode-session/status`),"
    "s=(a?.accounts||[]).find(n=>e.email&&n.key===e.email)||(a?.accounts||[]).find(n=>e.id&&n.id===e.id)"
    "||(a?.accounts||[]).find(n=>Array.isArray(n?.quota?.groups));r=s?.quota}"
    "if(!r||!Array.isArray(r.groups))throw Error(t(`commandcode_quota.empty_models`));"
    "let i=p_(r);if(i.length===0)throw Error(t(`commandcode_quota.empty_models`));"
    "i.forEach(e=>{let n={[`5h`]:0,[`7d`]:1,[`weekly`]:1,[`week`]:1,[`30d`]:2,[`monthly`]:2};"
    "(e.buckets||[]).sort((e,t)=>(n[(e.window||``).toLowerCase()]??90)-(n[(t.window||``).toLowerCase()]??90))});"
    "return{groups:i,subscription:r.subscription??null,serverTimeOffsetMs:r.serverTimeOffsetMs??null}},"
    "storeSelector:e=>e.commandCodeQuota,storeSetter:`setCommandCodeQuota`,"
    "buildLoadingState:()=>({status:`loading`,groups:[],subscription:null,serverTimeOffsetMs:null}),"
    "buildSuccessState:e=>({status:`success`,groups:e.groups,subscription:e.subscription,serverTimeOffsetMs:e.serverTimeOffsetMs}),"
    "buildErrorState:(e,t)=>({status:`error`,groups:[],subscription:null,serverTimeOffsetMs:null,error:e,errorStatus:t}),"
    "Body:pO}"
)

I18N = [
    (
        "opencode_quota:{title:`OpenCode Go 额度`,empty_title:`暂无 OpenCode Go 渠道`,empty_desc:`在 OpenCode Go 插件页接入 API Key 后即可在此查看额度。`,idle:`点击此处刷新额度`,loading:`正在加载额度...`,load_failed:`额度获取失败：{{message}}`,missing_auth_index:`认证文件缺少 auth_index`,empty_models:`暂无额度数据`}",
        "commandcode_quota:{title:`Command Code 额度`,empty_title:`暂无 Command Code 渠道`,empty_desc:`在 Command Code 插件页接入 API Key 后即可在此查看额度。`,idle:`点击此处刷新额度`,loading:`正在加载额度...`,load_failed:`额度获取失败：{{message}}`,missing_auth_index:`认证文件缺少 auth_index`,empty_models:`暂无额度数据`}",
    ),
    (
        "opencode_quota:{title:`OpenCode Go 配額`,empty_title:`暫無 OpenCode Go 渠道`,empty_desc:`在 OpenCode Go 外掛頁接入 API Key 後即可在此查看配額。`,idle:`點此重新整理配額`,loading:`正在載入配額...`,load_failed:`配額取得失敗：{{message}}`,missing_auth_index:`驗證檔案缺少 auth_index`,empty_models:`暫無配額資料`}",
        "commandcode_quota:{title:`Command Code 配額`,empty_title:`暫無 Command Code 渠道`,empty_desc:`在 Command Code 外掛頁接入 API Key 後即可在此查看配額。`,idle:`點此重新整理配額`,loading:`正在載入配額...`,load_failed:`配額取得失敗：{{message}}`,missing_auth_index:`驗證檔案缺少 auth_index`,empty_models:`暫無配額資料`}",
    ),
    (
        "opencode_quota:{title:`OpenCode Go Quota`,empty_title:`No OpenCode Go credentials`,empty_desc:`Connect an OpenCode Go API key on the plugin page to view quota here.`,idle:`Click here to refresh quota`,loading:`Loading quota...`,load_failed:`Failed to load quota: {{message}}`,missing_auth_index:`Auth file missing auth_index`,empty_models:`No quota data available`}",
        "commandcode_quota:{title:`Command Code Quota`,empty_title:`No Command Code credentials`,empty_desc:`Connect a Command Code API key on the plugin page to view quota here.`,idle:`Click here to refresh quota`,loading:`Loading quota...`,load_failed:`Failed to load quota: {{message}}`,missing_auth_index:`Auth file missing auth_index`,empty_models:`No quota data available`}",
    ),
    (
        "opencode_quota:{title:`Квота OpenCode Go`,empty_title:`Нет учётных данных OpenCode Go`,empty_desc:`Подключите ключ OpenCode Go на странице плагина, чтобы увидеть квоту.`,idle:`Нажмите, чтобы обновить квоту`,loading:`Загрузка квоты...`,load_failed:`Не удалось загрузить квоту: {{message}}`,missing_auth_index:`В файле авторизации отсутствует auth_index`,empty_models:`Данные по квоте отсутствуют`}",
        "commandcode_quota:{title:`Квота Command Code`,empty_title:`Нет учётных данных Command Code`,empty_desc:`Подключите ключ Command Code на странице плагина, чтобы увидеть квоту.`,idle:`Нажмите, чтобы обновить квоту`,loading:`Загрузка квоты...`,load_failed:`Не удалось загрузить квоту: {{message}}`,missing_auth_index:`В файле авторизации отсутствует auth_index`,empty_models:`Данные по квоте отсутствуют`}",
    ),
]


def must_replace(html: str, old: str, new: str, label: str, count: int | None = 1) -> str:
    found = html.count(old)
    if found == 0:
        raise SystemExit(f"missing needle {label}")
    if count is not None and found != count:
        raise SystemExit(f"{label}: expected {count} matches, found {found}")
    return html.replace(old, new)


def replace_if(html: str, old: str, new: str, label: str, count: int | None = 1) -> str:
    if old == new or new in html:
        return html
    return must_replace(html, old, new, label, count=count)


def inject_token_panel(html: str) -> str:
    if TOKEN_MARK in html:
        return html
    if "<head>" not in html:
        raise SystemExit("missing <head>")
    return html.replace("<head>", "<head>\n" + TOKEN_SCRIPT, 1)


def patch(html: str) -> str:
    if "Yj=[`claude`,`antigravity`,`codex`,`xai`,`kimi`,`opencode-go`]" not in html:
        raise SystemExit("OpenCode Go quota patch is missing; apply cpa-plugin-opencode-session first")
    if "Yj=[`claude`,`antigravity`,`codex`,`xai`,`kimi`,`opencode-go`,`commandcode`]" in html and TOKEN_MARK in html:
        return finalize(html)

    html = inject_token_panel(html)
    html = replace_if(html, AUTH_LIST_OLD, AUTH_LIST_NEW, "Oy.list merge both plugins")
    html = replace_if(html, GET_MODELS_OLD, GET_MODELS_NEW, "getModelsForAuthFile both plugins")
    html = replace_if(html, SET_STATUS_OLD, SET_STATUS_NEW, "setStatus both plugins")
    html = replace_if(html, DELETE_FILES_OLD, DELETE_FILES_NEW, "deleteFiles both plugins")

    html = replace_if(html, "C=!x||S===`aistudio`||S===`opencode-go`", "C=!x||S===`aistudio`||S===`opencode-go`||S===`commandcode`", "models button")
    html = replace_if(html, "te=x&&S!==`opencode-go`?t(`auth_files.type_virtual`)", "te=x&&S!==`opencode-go`&&S!==`commandcode`?t(`auth_files.type_virtual`)", "health text")
    html = replace_if(html, "ne=x&&S!==`opencode-go`?uk.stateVirtual", "ne=x&&S!==`opencode-go`&&S!==`commandcode`?uk.stateVirtual", "health class")
    html = replace_if(html, "j=!!A&&(!x||S===`opencode-go`)&&!r", "j=!!A&&(!x||S===`opencode-go`||S===`commandcode`)&&!r", "quota row")
    html = replace_if(
        html,
        "nD=new Set([`antigravity`,`claude`,`codex`,`kimi`,`xai`,`opencode-go`])",
        "nD=new Set([`antigravity`,`claude`,`codex`,`kimi`,`xai`,`opencode-go`,`commandcode`])",
        "quota types",
    )
    html = replace_if(
        html,
        "rD=[`vertex`,`aistudio`,`antigravity`,`xai`,`claude`,`codex`,`kimi`,`opencode-go`]",
        "rD=[`vertex`,`aistudio`,`antigravity`,`xai`,`claude`,`codex`,`kimi`,`opencode-go`,`commandcode`]",
        "filter order",
    )
    html = replace_if(
        html,
        "S===`opencode-go`&&(0,H.jsx)(U,{variant:`danger`",
        "(S===`opencode-go`||S===`commandcode`)&&(0,H.jsx)(U,{variant:`danger`",
        "delete button",
    )
    html = replace_if(
        html,
        "(!x||S===`opencode-go`)&&(0,H.jsxs)(`div`,{className:uk.toggleWrap",
        "(!x||S===`opencode-go`||S===`commandcode`)&&(0,H.jsxs)(`div`,{className:uk.toggleWrap",
        "enable toggle",
    )

    html = replace_if(
        html,
        "var Yj=[`claude`,`antigravity`,`codex`,`xai`,`kimi`,`opencode-go`]",
        "var Yj=[`claude`,`antigravity`,`codex`,`xai`,`kimi`,`opencode-go`,`commandcode`]",
        "Yj",
    )
    html = replace_if(
        html,
        'Zj={antigravity:qD.filterFn,claude:yO.filterFn,codex:FO.filterFn,kimi:BO.filterFn,xai:JO.filterFn,["opencode-go"]:rk["opencode-go"].filterFn}',
        'Zj={antigravity:qD.filterFn,claude:yO.filterFn,codex:FO.filterFn,kimi:BO.filterFn,xai:JO.filterFn,["opencode-go"]:rk["opencode-go"].filterFn,["commandcode"]:rk["commandcode"].filterFn}',
        "Zj",
    )
    html = replace_if(
        html,
        "n===`xai`?e.xaiQuota[t.name]:n===`opencode-go`?e.opencodeGoQuota[t.name]:ck(n)",
        "n===`xai`?e.xaiQuota[t.name]:n===`opencode-go`?e.opencodeGoQuota[t.name]:n===`commandcode`?e.commandCodeQuota[t.name]:ck(n)",
        "store lookup",
    )
    html = replace_if(
        html,
        "antigravityQuota:{},claudeQuota:{},codexQuota:{},kimiQuota:{},xaiQuota:{},opencodeGoQuota:{}",
        "antigravityQuota:{},claudeQuota:{},codexQuota:{},kimiQuota:{},xaiQuota:{},opencodeGoQuota:{},commandCodeQuota:{}",
        "store maps",
        count=2,
    )
    html = replace_if(
        html,
        "setOpencodeGoQuota:t=>e(e=>({opencodeGoQuota:tm(t,e.opencodeGoQuota)}))",
        "setOpencodeGoQuota:t=>e(e=>({opencodeGoQuota:tm(t,e.opencodeGoQuota)})),setCommandCodeQuota:t=>e(e=>({commandCodeQuota:tm(t,e.commandCodeQuota)}))",
        "setter",
    )
    html = replace_if(
        html,
        ",Og=nm(e=>e.opencodeGoQuota),w=(0,y.useMemo)(()=>({antigravity:v,claude:b,codex:x,kimi:S,xai:C,[\"opencode-go\"]:Og}),[v,b,x,S,C,Og])",
        ",Og=nm(e=>e.opencodeGoQuota),Cg=nm(e=>e.commandCodeQuota),w=(0,y.useMemo)(()=>({antigravity:v,claude:b,codex:x,kimi:S,xai:C,[\"opencode-go\"]:Og,[\"commandcode\"]:Cg}),[v,b,x,S,C,Og,Cg])",
        "quota store memo",
    )
    html = replace_if(
        html,
        'filter_kimi:`Kimi`,"filter_opencode-go":`OpenCode Go`,',
        'filter_kimi:`Kimi`,"filter_opencode-go":`OpenCode Go`,"filter_commandcode":`Command Code`,',
        "filter labels",
        count=3,
    )
    html = replace_if(
        html,
        '"filter_kimi":"Kimi","filter_opencode-go":"OpenCode Go","filter_aistudio":"AIStudio"',
        '"filter_kimi":"Kimi","filter_opencode-go":"OpenCode Go","filter_commandcode":"Command Code","filter_aistudio":"AIStudio"',
        "russian filter label",
    )

    oc_end = (
        "storeSetter:`setOpencodeGoQuota`,buildLoadingState:()=>({status:`loading`,groups:[],subscription:null,serverTimeOffsetMs:null}),"
        "buildSuccessState:e=>({status:`success`,groups:e.groups,subscription:e.subscription,serverTimeOffsetMs:e.serverTimeOffsetMs}),"
        "buildErrorState:(e,t)=>({status:`error`,groups:[],subscription:null,serverTimeOffsetMs:null,error:e,errorStatus:t}),Body:pO}}"
    )
    html = replace_if(html, oc_end, oc_end[:-1] + "," + CC_ADAPTER + "}", "rk commandcode adapter")

    for old, payload in I18N:
        html = replace_if(html, old, old + "," + payload, "i18n " + payload[:28])

    return finalize(html)


def finalize(html: str) -> str:
    checks = {
        "auth-files merge": "`commandcode-session`,`commandcode`",
        "models fallback": "`commandcode-session`",
        "Yj": "`opencode-go`,`commandcode`",
        "quota types": "`opencode-go`,`commandcode`",
        "adapter": '["commandcode"]:{type:`commandcode`',
        "i18n": "commandcode_quota:{title:`Command Code 额度`",
        "token panel": TOKEN_MARK,
        "setStatus": "/plugins/commandcode-session/auth-files/status",
        "deleteFiles": "/plugins/commandcode-session/auth-files",
        "toggle": "S===`opencode-go`||S===`commandcode`",
    }
    for label, needle in checks.items():
        if needle not in html:
            raise SystemExit(f"missing after patch: {label}")
    if html.count("commandcode_quota:{") != 4:
        raise SystemExit(f"commandcode_quota i18n count {html.count('commandcode_quota:{')}")
    return html


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("html_path", nargs="?", default="/opt/cliproxy-api/static/management.html")
    parser.add_argument("--backup", default="")
    args = parser.parse_args()
    path = Path(args.html_path)
    html = path.read_text(encoding="utf-8", errors="replace")
    updated = patch(html)
    if updated == html:
        print(f"already patched: {path}")
        return 0
    backup = Path(args.backup) if args.backup else path.with_suffix(".html.commandcode.bak")
    if not backup.exists():
        shutil.copy2(path, backup)
        print(f"backup {backup}")
    path.write_text(updated, encoding="utf-8")
    print(f"patched {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

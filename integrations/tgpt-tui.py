#!/usr/bin/env python3
import os, sys, json, subprocess, shutil, tempfile, urllib.request, urllib.error
from pathlib import Path

def enable_ansi():
    if os.name == "nt":
        try: os.system("")
        except: pass
enable_ansi()
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HOME = Path.home()
# tgpt config: ~/.config/tgpt/config.conf (or ./config.conf higher priority)
TGPT_DIR = HOME / ".config" / "tgpt"
TGPT_CFG = Path(os.environ.get("AGENTICOS_TGPT_CONFIG", TGPT_DIR / "config.conf"))
TGPT_CFG_LOCAL = Path.cwd() / "config.conf"
HERE = Path(__file__).parent

# Fallback OpenAI-compatible API (user: if any provider not working, use this)
FALLBACK_URL = os.environ.get("AGENTICOS_FALLBACK_URL", "")
FALLBACK_KEY = os.environ.get("AGENTICOS_FALLBACK_KEY", "")
FALLBACK_MODEL = os.environ.get("AGENTICOS_FALLBACK_MODEL", "auto")

# ── Dynamic providers/tools from `tgpt --help` (fallback hardcoded if parse fails) ──
# User request: free (no key) -> "free", free/api (free but needs key) -> "free/api", else "" (just name)
_FALLBACK_PROVIDERS = {
    "anyapi":       ("AnyAPI",       "free/api", "ANYAPI_API_KEY",       "ANYAPI_MODEL",       "openai/gpt-4o-mini", "100k free tokens/day, multi-model"),
    "aihorde":      ("AI Horde",     "free",     "AIHORDE_API_KEY",      "AIHORDE_MODEL",      "", "Community volunteer compute"),
    "aitopia":      ("Aitopia",      "free",     None,                   None,                 "gpt-4o-mini", "Free, no key"),
    "atlascloud":   ("AtlasCloud",   "",         "ATLASCLOUD_API_KEY",   "ATLASCLOUD_MODEL",   "qwen/qwen3.8-max", "OpenAI-compatible"),
    "deepseek":     ("DeepSeek",     "",         "DEEPSEEK_API_KEY",     "DEEPSEEK_MODEL",     "DeepSeek-V4-Flash", "Requires API key"),
    "deepseek-web": ("DeepSeek-Web","free/api", "DEEPSEEK_WEB_TOKEN",   None,                 "", "chat.deepseek.com + PoW, needs userToken"),
    "fx":           ("FX",           "free",     None,                   None,                 "zai/glm-5.2", "Free via fx.sh gateway"),
    "gemini":       ("Gemini",       "free/api", "GEMINI_API_KEY",       "GEMINI_MODEL",       "", "Free API key aistudio.google.com"),
    "groq":         ("Groq",         "free/api", "GROQ_API_KEY",         "GROQ_MODEL",         "", "Free API key console.groq.com"),
    "isou":         ("Isou",         "free",     None,                   None,                 "", "Free + web search isou.chat"),
    "koboldai":     ("KoboldAI",     "free",     None,                   None,                 "Tiefighter-13B", "HF novels only"),
    "litellm":      ("LiteLLM",      "",         "LITELLM_API_KEY",      "LITELLM_MODEL",      "", "Gateway/proxy, custom URL"),
    "minimax":      ("MiniMax",      "",         "MINIMAX_API_KEY",      "MINIMAX_MODEL",      "MiniMax-M2.7", "Requires key"),
    "ollama":       ("Ollama",       "free",     None,                   None,                 "", "Local  http://localhost:11434"),
    "ollamacloud":  ("OllamaCloud",  "free/api", "OLLAMA_API_KEY",       "OLLAMA_MODEL",       "gpt-oss:120b", "Ollama Cloud API"),
    "omniroute":    ("OmniRoute",    "",         "OMNIROUTE_API_KEY",    "OMNIROUTE_MODEL",    "auto", "OpenAI compat localhost:20128"),
    "opencode":     ("OpenCode",     "free",     "OPENCODE_API_KEY",     "OPENCODE_MODEL",     "deepseek-v4-flash-free", "Free zen API, key=public"),
    "openai":       ("OpenAI",       "",         "OPENAI_API_KEY",       "OPENAI_MODEL",       "", "Needs API key"),
    "openrouter":   ("OpenRouter",   "free/api", "OPENROUTER_API_KEY",   "OPENROUTER_MODEL",   "openrouter/free", "Free tier available"),
    "pollinations": ("Pollinations", "free",     "POLLINATIONS_API_KEY", "POLLINATIONS_MODEL", "", "Works without key"),
    "powerbrain":   ("PowerBrain",   "free",     None,                   None,                 "gpt-5", "Free, no key powerbrainai.com"),
}
_FALLBACK_IMG = {
    "pollinations": ("Pollinations", "free", "POLLINATIONS_API_KEY", "flux", "flux/turbo"),
    "magicstudio":  ("MagicStudio",  "free", None, "","very fast free"),
    "anyapi":       ("AnyAPI Img",   "free/api", "ANYAPI_API_KEY", "google/gemini-2.5-flash-image", "many models"),
}
_FALLBACK_TOOLS = [
    ("web_search_exa",       "Web search via Exa (EXA_API_KEY)"),
    ("web_search_firecrawl", "Web search via Firecrawl (FIRECRAWL_API_KEY)"),
    ("read_directory",       "List directory contents"),
    ("read_file",            "Read text file"),
    ("execute_command",      "Execute shell command"),
    ("web_fetch",            "Fetch URL contents"),
    ("write_file",           "Write file"),
    ("edit_file",            "Edit file (old->new)"),
    ("grep",                 "Regex search file contents"),
    ("glob",                 "Glob find files/dirs"),
]

def _classify_provider(desc):
    d = desc.lower()
    # Explicit free without key signals
    if "without an api key" in d or "without api key" in d or "no api key required" in d or "defaults to 'public'" in d or 'defaults to "public"' in d:
        return "free"
    has_free = "free" in d
    has_api_key = "api key" in d or "api_key" in d
    has_requires_free = "requires a free api key" in d
    has_requires_key = "requires api key" in d or "needs api key" in d
    if has_requires_free:
        return "free/api"
    if has_free and has_api_key:
        # If free and api key mentioned but not "without", treat as free/api unless it's a free provider with optional key
        # Optional key providers like aihorde, opencode have "Supports" not "Requires"
        if "supports" in d and "free" in d:
            return "free"
        return "free/api"
    if has_requires_key:
        if has_free:
            return "free/api"
        return ""
    if has_free:
        return "free"
    if "works without" in d or "community" in d:
        return "free"
    return ""

def _extract_env_vars(desc):
    import re
    # Find patterns like ANYAPI_API_KEY, GROQ_MODEL etc.
    keys = re.findall(r"[A-Z][A-Z0-9_]*_API_KEY", desc)
    models = re.findall(r"[A-Z][A-Z0-9_]*_MODEL", desc)
    # also DEEPSEEK_WEB_TOKEN etc.
    token = re.findall(r"[A-Z][A-Z0-9_]*_TOKEN", desc)
    key_var = keys[0] if keys else (token[0] if token else None)
    model_var = models[0] if models else None
    return key_var, model_var

def _extract_default_model(desc):
    import re
    m = re.search(r"Default model[:\s]+([^\.\n]+)", desc, re.IGNORECASE)
    if m:
        return m.group(1).strip().split()[0].strip('.,')
    # fallback: look for "uses ... model"
    m2 = re.search(r"uses ([a-z0-9/_\-\.]+) model", desc, re.IGNORECASE)
    if m2:
        return m2.group(1)
    return ""

def _parse_tgpt_help():
    import subprocess, shutil, re
    try:
        tgpt = shutil.which("tgpt") or "tgpt"
        out = subprocess.run([tgpt, "--help"], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=5)
        txt = out.stdout + "\n" + out.stderr
        if not txt or "Provider:" not in txt:
            return None
        # ── Robust split-based parsing ──
        # Provider names from "Available providers to use:" line as authoritative list
        avail = None
        m_avail = re.search(r"Available providers to use:\s*([^\n]+)", txt)
        if m_avail:
            avail = [x.strip().lower() for x in m_avail.group(1).split(",") if x.strip()]
        # Split on Provider:
        parts = txt.split("Provider:")
        providers = {}
        img_providers = {}
        image_start = txt.find("Image generation providers:")
        tool_section = txt.find("Built-in tools")
        # Determine image section start index in terms of parts
        # We'll map each Provider occurrence position
        # Use regex to find positions of each Provider:
        pos = []
        for m in re.finditer(r"Provider:", txt):
            pos.append(m.start())
        # For each provider chunk after split, the name is first line
        for idx, chunk in enumerate(parts[1:]):  # skip first part before first Provider
            # chunk starts with " providerName\n description..."
            lines = chunk.strip().split("\n")
            if not lines:
                continue
            name = lines[0].strip().lower()
            # description is rest until next Provider (but chunk already isolated, so take all lines until we hit a known header)
            # Filter out trailing sections: stop at empty line followed by known header?
            # Simpler: join all lines of chunk after name until we encounter a line that looks like a new section header
            desc_lines = []
            for l in lines[1:]:
                # stop if line starts with "Tool calling" or "Providers:" or similar header? But those are not inside provider desc
                # Provider desc is typically 1-2 lines, so we can just take until blank line + next Provider handled by split
                # Actually chunk after split already excludes next Provider, so take whole remaining chunk
                desc_lines.append(l)
            desc = " ".join(desc_lines).strip()
            # Trim desc to first 500 chars and remove extra whitespace
            desc = re.sub(r"\s+", " ", desc)
            # Determine if image provider: check position vs image_start
            start_pos = pos[idx] if idx < len(pos) else 0
            is_img = image_start != -1 and start_pos > image_start and (tool_section == -1 or start_pos < tool_section)
            disp = name.title().replace("-", " ").replace("Ai ", "AI ").replace("Openai","OpenAI")
            # Fix specific display
            disp_map = {"Deepseek-Web":"DeepSeek-Web","Aihorde":"AI Horde","Anyapi":"AnyAPI","Atlascloud":"AtlasCloud","Ollamacloud":"OllamaCloud","Openai":"OpenAI","Openrouter":"OpenRouter","Pollinations":"Pollinations","Powerbrain":"PowerBrain","Magicstudio":"MagicStudio"}
            disp = disp_map.get(name, disp) if name not in disp_map else disp_map[name]
            # Actually build disp_map lower keys
            lower_disp = {"aihorde":"AI Horde","anyapi":"AnyAPI","atlascloud":"AtlasCloud","deepseek-web":"DeepSeek-Web","ollamacloud":"OllamaCloud","openai":"OpenAI","openrouter":"OpenRouter","pollinations":"Pollinations","powerbrain":"PowerBrain","magicstudio":"MagicStudio","opencode":"OpenCode"}
            if name in lower_disp:
                disp = lower_disp[name]
            else:
                disp = name.title()
                # capitalize correctly
            tag = _classify_provider(desc)
            key_var, model_var = _extract_env_vars(desc)
            def_model = _extract_default_model(desc)
            tup = (disp, tag, key_var, model_var, def_model, desc[:150])
            if is_img:
                img_providers[name] = tup
            else:
                providers[name] = tup
        # If we have avail list, ensure providers dict matches avail (for main providers)
        # Some providers may be missing from parsed due to formatting, so fallback to avail
        if avail:
            for pid in avail:
                if pid not in providers and pid in _FALLBACK_PROVIDERS:
                    providers[pid] = _FALLBACK_PROVIDERS[pid]
        # Tools parsing (dynamic)
        tools=[]
        if "Built-in tools" in txt:
            sec = txt[txt.find("Built-in tools"): txt.find("Built-in tools")+3000]
            for line in sec.split("\n"):
                line=line.strip()
                if not line or line.startswith("Built-in") or line.startswith("MCP") or line.startswith("Supported"): continue
                # Stop at blank line after tools list or next section
                if line.startswith("MCP servers:") or line.startswith("Supported server"): break
                parts = re.split(r"\s{2,}", line)
                if len(parts)>=2 and parts[0].startswith(("web_","read_","execute","web_fetch","write","edit","grep","glob")):
                    tools.append((parts[0].strip(), parts[1].strip()))
        if providers:
            return providers, img_providers or _FALLBACK_IMG, tools or _FALLBACK_TOOLS
        return None
    except Exception as e:
        # import traceback; print(e)
        return None

def _load_dynamic():
    parsed = _parse_tgpt_help()
    if parsed:
        prov, img, tools = parsed
        # Merge fallback tags for known providers to keep accurate free/free/api marking
        # Dynamic parsing is authoritative for *which* providers exist on this tgpt binary,
        # but fallback has curated tag/key/model for known providers.
        merged = {}
        for pid, tup in prov.items():
            if pid in _FALLBACK_PROVIDERS:
                # Keep fallback's curated tuple (more accurate free marking)
                merged[pid] = _FALLBACK_PROVIDERS[pid]
            else:
                merged[pid] = tup
        # Also keep any fallback providers that are in dynamic's Available list but not parsed? Already handled
        return merged, img or _FALLBACK_IMG, tools or _FALLBACK_TOOLS
    return _FALLBACK_PROVIDERS, _FALLBACK_IMG, _FALLBACK_TOOLS

PROVIDERS, IMG_PROVIDERS, TOOLS = _load_dynamic()
# Optional user-configured fallback provider (disabled by default).
if FALLBACK_URL and "fallback" not in PROVIDERS:
    PROVIDERS["fallback"] = ("Fallback", "free/api", None, None, FALLBACK_MODEL, f"Local fallback {FALLBACK_URL} via openai configured credentials")
# keep fallback for reference
SEARCH_PROVIDERS = ["exa", "google"]

# Models per provider (suggestions)
PROVIDER_MODELS = {
    "anyapi": ["openai/gpt-4o-mini","openai/gpt-4o","google/gemini-2.0-flash","xai/grok-2"],
    "opencode": ["deepseek-v4-flash-free","mimo-v2.5-free","qwen3-32b-free","glm-5-free"],
    "pollinations": ["pollinations/gpt-4o-mini","pollinations/llama-3","openai","mitral"],
    "groq": ["llama-3.3-70b-versatile","llama-3.1-8b-instant","mixtral-8x7b-32768","gemma2-9b-it"],
    "gemini": ["gemini-2.0-flash","gemini-1.5-pro","gemini-1.5-flash"],
    "openai": ["gpt-4o","gpt-4o-mini","gpt-4.1","o3-mini"],
    "deepseek": ["deepseek-chat","deepseek-reasoner"],
    "fx": ["zai/glm-5.2","zai/glm-4.5","deepseek-v3"],
    "openrouter": ["openrouter/auto","openrouter/free","meta-llama/llama-3.3-70b-instruct:free"],
    "ollama": ["llama3.2","qwen2.5-coder","deepseek-r1","mistral"],
    "fallback": ["auto","fusion","claude-sonnet-4-5","claude-opus-4-5","gpt-4o-mini"],
}

RED="\033[31m"; GREEN="\033[32m"; YELLOW="\033[33m"; BLUE="\033[34m"; MAGENTA="\033[35m"; CYAN="\033[36m"; BOLD="\033[1m"; DIM="\033[2m"; RESET="\033[0m"
def c(text,color): return color+text+RESET
def clear():
    sys.stdout.write("\033[H\033[2J"); sys.stdout.flush()

TGPT_CFG = Path(os.environ.get("AGENTICOS_TGPT_CONFIG", Path.home() / ".config/agenticos/tgpt.conf"))
TGPT_DIR = TGPT_CFG.parent
TGPT_CFG_LOCAL = TGPT_CFG

def read_cfg():
    # tgpt checks ./config.conf first, then ~/.config/tgpt/config.conf
    cfg={}
    for p in [TGPT_CFG_LOCAL, TGPT_CFG]:
        if p.exists():
            for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                line=line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k,v=line.split("=",1)
                    cfg.setdefault(k.strip(), v.strip())
    return cfg

def write_cfg(cfg):
    TGPT_DIR.mkdir(parents=True, exist_ok=True)
    # preserve local file if it exists? Write to primary (~/.config/tgpt)
    lines=[f"{k}={v}" for k,v in cfg.items()]
    TGPT_CFG.write_text("\n".join(lines)+"\n", encoding="utf-8")

def set_cfg_key(key,value):
    cfg=read_cfg()
    if value is None or value=="":
        cfg.pop(key,None)
    else:
        cfg[key]=value
    # If local config exists and had the key, also update local? Simpler write to global
    # If TGPT_CFG_LOCAL exists, we update it instead to respect priority
    if TGPT_CFG_LOCAL.exists():
        # update local file directly
        local={}
        for line in TGPT_CFG_LOCAL.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.strip() and not line.startswith("#") and "=" in line:
                k,v=line.split("=",1); local[k.strip()]=v.strip()
        if value is None or value=="":
            local.pop(key,None)
        else:
            local[key]=value
        TGPT_CFG_LOCAL.write_text("\n".join(f"{k}={v}" for k,v in local.items())+"\n", encoding="utf-8")
    else:
        write_cfg(cfg)

def get_cfg(key, default=""):
    return read_cfg().get(key, os.environ.get(key, default))

def tgpt_env():
    env=dict(os.environ)
    for k,v in read_cfg().items():
        env.setdefault(k, v)
    return env

def _strip_provider_args(args):
    out=[]
    skip=False
    for a in args:
        if skip:
            skip=False
            continue
        if a in ("--provider","--url","--key","--model"):
            skip=True
            continue
        if a.startswith(("--provider=","--url=","--key=","--model=")):
            continue
        out.append(a)
    return out

def _fallback_chat(prompt, model=FALLBACK_MODEL):
    # Direct HTTP to FALLBACK_URL (OpenAI-compatible) – bypass tgpt provider handling
    try:
        import json, urllib.request, urllib.error
        url = FALLBACK_URL.rstrip("/") + "/chat/completions"
        payload = json.dumps({"model": model, "messages": [{"role":"user","content":prompt}], "stream": False}).encode()
        req = urllib.request.Request(url, data=payload, headers={"Content-Type":"application/json","Authorization": f"Bearer {FALLBACK_KEY}"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            j=json.loads(resp.read().decode())
            choices=j.get("choices") or []
            if choices:
                return choices[0].get("message",{}).get("content") or choices[0].get("text") or ""
            return ""
    except Exception as e:
        print(c(f"fallback error: {e}", RED))
        return None

def _extract_prompt(args):
    # prompt is last non-flag arg (not starting with -) or last arg if no flag
    for a in reversed(args):
        if not str(a).startswith("-"):
            return str(a)
    return ""

def run_tgpt(args, stream=True, _fallback_tried=False):
    cmd=[shutil.which("tgpt") or "tgpt"]+args
    try:
        if stream:
            proc=subprocess.run(cmd, env=tgpt_env())
            rc=proc.returncode
            # Fallback if provider failed (non-zero) or if no output was produced but fallback is configured
            # For stream we can't detect empty output, so only fallback on rc !=0
            if rc!=0 and not _fallback_tried and FALLBACK_URL and not any(FALLBACK_URL in str(a) for a in args) and "--url" not in args:
                print(c(f"Provider failed rc={rc}, retrying with fallback {FALLBACK_URL} model {FALLBACK_MODEL}", YELLOW))
                # Try tgpt with openai fallback first, then direct HTTP if that also fails
                fb=["--provider","openai","--url",FALLBACK_URL,"--key",FALLBACK_KEY,"--model",FALLBACK_MODEL] + _strip_provider_args(args)
                rc2=run_tgpt(fb, stream=stream, _fallback_tried=True)
                if rc2==0:
                    return rc2
                # If tgpt fallback still fails or gives no output (rc0 but no content), try direct HTTP
                prompt=_extract_prompt(args)
                if prompt:
                    content=_fallback_chat(prompt)
                    if content:
                        print(content)
                        return 0
                return rc2
            return rc
        else:
            proc=subprocess.run(cmd, env=tgpt_env(), capture_output=True, text=True)
            rc=proc.returncode
            out=(proc.stdout or "").strip()
            err=(proc.stderr or "").strip()
            # Fallback if rc !=0 or empty output (and error suggests failure)
            need_fallback = rc!=0 or (not out and ("requires" in err.lower() or "api key" in err.lower() or "error" in err.lower() or not out))
            # But to avoid false fallback on empty prompt, only fallback if rc!=0 or err indicates failure
            if rc!=0 and not _fallback_tried and FALLBACK_URL and not any(FALLBACK_URL in str(a) for a in args) and "--url" not in args:
                print(c(f"Provider failed rc={rc}, retrying with fallback {FALLBACK_URL}", YELLOW))
                fb=["--provider","openai","--url",FALLBACK_URL,"--key",FALLBACK_KEY,"--model",FALLBACK_MODEL] + _strip_provider_args(args)
                rc2, out2, err2 = run_tgpt(fb, stream=stream, _fallback_tried=True)
                if rc2==0 and (out2 or "").strip():
                    return rc2, out2, err2
                # Direct HTTP fallback
                prompt=_extract_prompt(args)
                if prompt:
                    content=_fallback_chat(prompt)
                    if content:
                        return 0, content, ""
                return rc2, out2, err2
            return proc.returncode, proc.stdout, proc.stderr
    except FileNotFoundError:
        print(c("tgpt not found in PATH. Install: go install github.com/aandrew-me/tgpt@latest", RED))
        # Try direct fallback as last resort
        if not _fallback_tried and FALLBACK_URL:
            prompt=_extract_prompt(args)
            if prompt:
                content=_fallback_chat(prompt)
                if content:
                    print(content)
                    return 0 if stream else (0, content, "")
        return 1 if stream else (1,"","tgpt not found")
    except Exception as e:
        print(c(f"error: {e}", RED))
        if not _fallback_tried and FALLBACK_URL:
            prompt=_extract_prompt(args)
            if prompt:
                content=_fallback_chat(prompt)
                if content:
                    print(content)
                    return 0 if stream else (0, content, "")
        return 1 if stream else (1,"",str(e))

def render(title, items, idx, footer=None):
    clear()
    # width calc stripped of colors for len
    def strip(s):
        import re
        return re.sub(r'\033\[[0-9;]*m','',s)
    width=max(len(title), *(len(strip(f"{i[0]} {i[1]}")) for i in items), len(strip(footer or "")))
    width=min(width+6, 90)
    border="─"*(width-2)
    print(BOLD+"┌"+border+"┐"+RESET)
    print(BOLD+"│"+(" "+title).ljust(width-1)+"│"+RESET)
    print(BOLD+"├"+border+"┤"+RESET)
    for n,(label,hint) in enumerate(items):
        marker=">" if n==idx else " "
        style=BOLD if n==idx else ""
        line=f"{marker} {label} {DIM+hint+RESET}" if hint else f"{marker} {label}"
        # pad calculation without ANSI
        raw_len=len(strip(line))
        pad=width - raw_len - 3
        print(style+"│ "+line+(" "*max(pad,0))+" │"+RESET)
    print(BOLD+"└"+border+"┘"+RESET)
    if footer:
        print(footer)
    print(DIM+"arrows/numbers: move  enter: select  q/esc: back  s: shell  c: code  /: find"+RESET)

def menu(title, items, footer=None):
    idx=0
    while True:
        render(title, items, idx, footer)
        key=read_key()
        if key=="up": idx=(idx-1)%len(items)
        elif key=="down": idx=(idx+1)%len(items)
        elif key=="enter": return idx
        elif key in ("q","esc"): return None
        elif key.isdigit() and key.isdigit():
            try:
                n=int(key)
                if n < len(items): return n
                # for 2-digit? allow 1,2 etc only single digit menu <10, else numeric entry not selection
            except: pass
            # also handle '0' as 10?
            if key=="0" and len(items)>9:
                return 9
        # also allow quick keys for modes?
        # return raw key for special handling? keep simple

def read_key():
    if os.name=="nt":
        try:
            import msvcrt
            first=msvcrt.getwch()
            if first in ("\x00","\xe0"):
                second=msvcrt.getwch()
                if second=="H": return "up"
                if second=="P": return "down"
                return ""
            if first in ("\r","\n"): return "enter"
            if first in ("q","Q"): return "q"
            if first=="\x1b": return "esc"
            return first
        except: return input()
    try:
        import termios, tty
        fd=sys.stdin.fileno()
        old=termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch=sys.stdin.read(1)
            if ch=="\x1b":
                seq=sys.stdin.read(2)
                if seq=="[A": return "up"
                if seq=="[B": return "down"
                return "esc"
            if ch in ("\r","\n"): return "enter"
            if ch in ("q","Q"): return "q"
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
    except: return input()

def text_input(prompt, default=None):
    suffix = f" [{default}]" if default else ""
    try:
        val=input(prompt+suffix+": ")
    except EOFError:
        return default
    return val.strip() if val.strip() else default

def wait_enter():
    try: input(DIM+"press enter to continue..."+RESET)
    except EOFError: pass

def choose_provider_with_tag():
    items=[]
    for pid in sorted(PROVIDERS.keys()):
        disp, tag, *_ = PROVIDERS[pid]
        hint=""
        if tag=="free": hint=c("free", GREEN)
        elif tag=="free/api": hint=c("free/api", YELLOW)
        else: hint=DIM+""+RESET
        # show as "id  Name  [tag]"
        label=f"{pid:<15} {disp}"
        items.append((label, hint))
    # add hint for tag legend
    footer=DIM+"green=free (no key)  yellow=free/api (needs free key)  dim=paid/custom"+RESET
    pick=menu("PROVIDER SELECTOR — tgpt --provider", items, footer=footer)
    if pick is None: return None
    return sorted(PROVIDERS.keys())[pick]

def choose_img_provider():
    items=[]
    pids=list(IMG_PROVIDERS.keys())
    for pid in pids:
        disp, tag, *_ = IMG_PROVIDERS[pid]
        hint=c(tag, GREEN) if tag=="free" else c(tag,YELLOW) if tag=="free/api" else ""
        items.append((f"{pid:<15} {disp}", hint))
    pick=menu("IMAGE PROVIDER — tgpt --provider (for --img)", items)
    if pick is None: return None
    return pids[pick]

# ── Action handlers ──

def do_quick_ask():
    clear()
    print(BOLD+"QUICK ASK — tgpt \"your question\""+RESET)
    prompt=text_input("Your question")
    if not prompt: return
    extras=[]
    if text_input("Add --quiet? (y/N)", default="n").lower() in ("y","yes"):
        extras.append("-q")
    if text_input("Add --whole (no stream)? (y/N)", default="n").lower() in ("y","yes"):
        extras.append("-w")
    use_provider=text_input("Provider override? (leave blank for config default, or type provider id)", default="")
    if use_provider: extras += ["--provider", use_provider]
    use_model=text_input("Model override? (blank = default)", default="")
    if use_model: extras += ["--model", use_model]
    clear(); print(c(f">> {prompt}", CYAN))
    run_tgpt(extras+[prompt])

def do_shell():
    clear()
    print(BOLD+"SHELL COMMAND — tgpt -s"+RESET)
    prompt=text_input("Describe the shell task")
    if not prompt: return
    y = text_input("Auto-execute without confirmation? (-y) (y/N)", default="n")
    extras=["-s"]
    if y.lower() in ("y","yes"): extras.append("-y")
    if text_input("Add --quiet? (y/N)", default="n").lower() in ("y","yes"): extras.append("-q")
    clear(); print(c(f">> {prompt}", CYAN))
    run_tgpt(extras+[prompt])

def do_code():
    clear()
    print(BOLD+"CODE — tgpt -c"+RESET)
    prompt=text_input("Describe the code to generate")
    if not prompt: return
    clear(); print(c(f">> {prompt}", CYAN))
    run_tgpt(["-c", prompt])

def do_find():
    clear()
    print(BOLD+"FIND / WEB SEARCH — tgpt -f"+RESET)
    prompt=text_input("Search query")
    if not prompt: return
    print("Search providers: exa (free/rate-limited, free/api if key), google (needs TGPT_GOOGLE_API_KEY + SEARCH_ENGINE_ID)")
    sp=text_input("Search provider (exa/google) [exa]", default="exa")
    extras=["-f"]
    if sp and sp!="exa": extras+=["--search-provider", sp]
    clear(); print(c(f">> {prompt}", CYAN))
    run_tgpt(extras+[prompt])

def do_interactive_menu():
    items=[
        ("Normal interactive — tgpt -i", "single-line, history"),
        ("Multiline — tgpt -m", "multi-line input"),
        ("Interactive shell — tgpt -is", "repl shell (not all providers)"),
        ("Interactive find — tgpt -if", "web search loop"),
        ("Interactive alias — tgpt -ia", "with aliases/functions"),
        ("Back", ""),
    ]
    pick=menu("INTERACTIVE MODES", items)
    if pick is None or pick==5: return
    flags=[["-i"],["-m"],["-is"],["-if"],["-ia"]][pick]
    clear(); print(c(f"Starting tgpt {' '.join(flags)} (Ctrl-D/C to exit)", CYAN))
    run_tgpt(flags)

def do_image():
    clear()
    print(BOLD+"IMAGE GENERATION — tgpt --img"+RESET)
    prompt=text_input("Image prompt (e.g. 'cat in space')")
    if not prompt: return
    prov=choose_img_provider()
    if prov is None: return
    out=text_input("Output file --out [auto]", default="")
    height=text_input("Height --height (pollinations only) [blank]", default="")
    width=text_input("Width --width (pollinations only) [blank]", default="")
    extras=["--img", "--provider", prov, prompt]
    if out: extras += ["--out", out]
    if height: extras += ["--height", height]
    if width: extras += ["--width", width]
    clear(); print(c(f">> {prompt}  [{prov}]", CYAN))
    run_tgpt(["--img", "--provider", prov] + ([ "--out", out] if out else []) + ([ "--height", height] if height else []) + ([ "--width", width] if width else []) + [prompt])

def do_tools():
    clear()
    print(BOLD+"TOOLS — tgpt -t [tools]"+RESET)
    print(DIM+"Select built-in tools to enable. 'all' enables everything."+RESET)
    items=[(f"{tid:<22} {desc}", "") for tid,desc in TOOLS] + [("all  (enable everything)", c("all",GREEN)), ("Back","")]
    pick=menu("TOOL SELECTOR — comma-separated for -t", items, footer=DIM+"Tip: you can also manually type list like 'web_search_exa,read_file'"+RESET)
    if pick is None or pick==len(items)-1: return
    if pick==len(items)-2:
        sel="all"
    else:
        sel=TOOLS[pick][0]
        # allow multi-select loop
        if text_input(f"Add more tools? Current: {sel} (y/N)", default="n").lower() in ("y","yes"):
            # second tool picker
            others=[t for i,t in enumerate(TOOLS) if i!=pick]
            print(c("Pick additional (enter blank to finish):", CYAN))
            # simple loop: let user type comma list
            extra=text_input("Additional tools comma-separated (or blank)", default="")
            if extra: sel=f"{sel},{extra}"
    prompt=text_input("What should the model do with tools?", default="")
    if not prompt:
        # just show what would run
        print(c(f"Would run: tgpt -t {sel} \"<prompt>\"", YELLOW))
        wait_enter()
        return
    clear(); print(c(f">> {prompt}  [-t {sel}]", CYAN))
    run_tgpt(["-t", sel, prompt])

def do_mcp():
    while True:
        items=[
            ("Enable MCP (auto-detect) — tgpt --mcp", "auto mcp_config.json"),
            ("Set MCP config path — --mcp-config", get_cfg("MCP_CONFIG","") or "not set"),
            ("Run single MCP server — --mcp-server", "e.g. npx -y server-filesystem"),
            ("Add MCP server — tgpt --mcp-add", "interactive"),
            ("Remove MCP server — tgpt --mcp-remove", "interactive"),
            ("Show current MCP config", ""),
            ("Test MCP + tools", "tgpt -t --mcp"),
            ("Back",""),
        ]
        pick=menu("MCP — Model Context Protocol", items)
        if pick is None or pick==7: break
        if pick==0:
            prompt=text_input("Prompt for MCP run (blank to just enable)")
            if prompt:
                run_tgpt(["--mcp", prompt])
            else:
                print(c("MCP enabled - config auto-detected if exists", GREEN))
                wait_enter()
        elif pick==1:
            cur=get_cfg("MCP_CONFIG","")
            new=text_input("Path to mcp_config.json", default=cur)
            if new is not None:
                set_cfg_key("MCP_CONFIG", new)
                print(c(f"MCP_CONFIG={new}", GREEN)); wait_enter()
        elif pick==2:
            cmd=text_input("MCP server command (e.g. npx -y @modelcontextprotocol/server-filesystem /tmp)", default="")
            if cmd:
                prompt=text_input("Prompt")
                if prompt: run_tgpt(["--mcp-server", cmd, prompt])
        elif pick==3:
            clear(); run_tgpt(["--mcp-add"])
        elif pick==4:
            clear(); run_tgpt(["--mcp-remove"])
        elif pick==5:
            cfg_path=get_cfg("MCP_CONFIG","")
            candidates=[Path(p) for p in [cfg_path, "./mcp_config.json", str(TGPT_DIR / "mcp_config.json"), "mcp_config.json"] if p and str(p).strip()]
            found=False
            for p in candidates:
                if p.exists() and p.is_file():
                    try:
                        print(BOLD+f"Found: {p}"+RESET); print(p.read_text(encoding="utf-8", errors="ignore")[:2000]); found=True; break
                    except IsADirectoryError:
                        continue
                    except Exception as e:
                        print(c(f"error reading {p}: {e}", RED)); continue
            if not found:
                print(c("No mcp_config.json found. Use --mcp-add to create one.", YELLOW))
                print("Expected locations: ./mcp_config.json or ~/.config/tgpt/mcp_config.json or $MCP_CONFIG")
            wait_enter()
        elif pick==6:
            prompt=text_input("Prompt for MCP+tools")
            if prompt: run_tgpt(["-t", "--mcp-config", get_cfg("MCP_CONFIG","mcp_config.json"), prompt])

def do_provider():
    pid=choose_provider_with_tag()
    if pid is None: return
    if pid == "fallback":
        clear(); print(BOLD+f"Fallback (freellmapi) -> openai @ {FALLBACK_URL}"+RESET)
        print(f"Model: {FALLBACK_MODEL}  Key: configured  URL: {FALLBACK_URL}")
        print(f"\nCurrent global AI_PROVIDER={get_cfg('AI_PROVIDER','')}")
        if not text_input(f"Set fallback (openai @ {FALLBACK_URL})? (Y/n)", default="y").lower() in ("y","yes",""):
            return
        set_cfg_key("AI_PROVIDER", "openai")
        set_cfg_key("AI_URL", FALLBACK_URL)
        set_cfg_key("OPENAI_API_KEY", FALLBACK_KEY)
        set_cfg_key("OPENAI_MODEL", FALLBACK_MODEL)
        set_cfg_key("AI_API_KEY", FALLBACK_KEY)
        set_cfg_key("AI_MODEL", FALLBACK_MODEL)
        print(c(f"Fallback set: openai @ {FALLBACK_URL} model {FALLBACK_MODEL}", GREEN))
        wait_enter()
        return
    # Show details
    disp, tag, keyvar, modelvar, defmodel, desc = PROVIDERS[pid]
    clear(); print(BOLD+f"{disp} ({pid})  {c(tag,GREEN) if tag=='free' else c(tag,YELLOW) if tag else ''}"+RESET)
    print(f"Description: {desc}")
    if defmodel: print(f"Default model: {defmodel}")
    if keyvar: print(f"Key env: {keyvar}")
    if modelvar: print(f"Model env: {modelvar}")
    print(f"\nCurrent global AI_PROVIDER={get_cfg('AI_PROVIDER','')}")
    if not text_input(f"Set AI_PROVIDER to '{pid}'? (Y/n)", default="y").lower() in ("y","yes",""):
        return
    set_cfg_key("AI_PROVIDER", pid)
    print(c(f"AI_PROVIDER={pid}", GREEN))
    # Offer to set key
    if keyvar:
        cur=get_cfg(keyvar, "")
        masked=cur[:4]+"..." if len(cur)>4 else cur
        nk=text_input(f"Set {keyvar} (current: {masked or 'empty'}) [leave blank to keep]", default="")
        if nk: set_cfg_key(keyvar, nk); print(c(f"{keyvar} updated", GREEN))
    # Offer to set model
    if modelvar:
        cur=get_cfg(modelvar, "")
        nm=text_input(f"Set {modelvar} (current: {cur or defmodel}) [blank keep]", default="")
        if nm: set_cfg_key(modelvar, nm); print(c(f"{modelvar}={nm}", GREEN))
    wait_enter()

def do_model():
    cur_provider=get_cfg("AI_PROVIDER","powerbrain")
    print(c(f"Current provider: {cur_provider}", CYAN))
    # show models for current provider + generic
    models=[]
    if cur_provider in PROVIDER_MODELS:
        models=PROVIDER_MODELS[cur_provider]
    items=[(m,"") for m in models] + [("Custom (type your own)",""), ("Show all provider models",""), ("Back","")]
    pick=menu(f"MODEL SELECTOR — provider {cur_provider}", items, footer=DIM+f"Current: {get_cfg(cur_provider.upper()+'_MODEL','') or get_cfg('OPENCODE_MODEL','') or get_cfg('AI_MODEL','')}"+RESET)
    if pick is None or pick==len(items)-1: return
    if pick==len(items)-2:
        # show all
        all_m=[]
        for prov,mlist in PROVIDER_MODELS.items():
            for m in mlist:
                all_m.append((f"{prov:<15} {m}",""))
        p2=menu("ALL MODELS", all_m)
        if p2 is None: return
        # flatten to get model string
        flat=[m for lst in PROVIDER_MODELS.values() for m in lst]
        model=flat[p2]
    elif pick==len(items)-3:
        model=text_input("Enter model id (e.g. gpt-4o-mini, deepseek-v4-flash)", default=get_cfg(cur_provider.upper()+"_MODEL",""))
        if not model: return
    else:
        model=models[pick]
    # Set per-provider model var if exists
    if cur_provider in PROVIDERS:
        _,_,_,modelvar,_,_=PROVIDERS[cur_provider]
        if modelvar:
            set_cfg_key(modelvar, model)
            print(c(f"{modelvar}={model}", GREEN))
        else:
            # fallback to generic
            set_cfg_key("AI_MODEL", model)
            print(c(f"AI_MODEL={model} (generic)", GREEN))
    else:
        set_cfg_key("AI_MODEL", model)
    # Also set OPENCODE_MODEL etc legacy?
    if cur_provider=="opencode":
        set_cfg_key("OPENCODE_MODEL", model)
    wait_enter()

def do_config():
    while True:
        cfg=read_cfg()
        provider=cfg.get("AI_PROVIDER","powerbrain")
        items=[
            (f"Show config  ({TGPT_CFG} + ./config.conf)", ""),
            (f"Edit config in $EDITOR ({TGPT_CFG})", ""),
            (f"Set API Key  --key  (AI_API_KEY)", cfg.get("AI_API_KEY","")[:8]+"..." if cfg.get("AI_API_KEY") else "empty"),
            (f"Set URL      --url", cfg.get("AI_URL","") or cfg.get("OPENCODE_URL","") or "empty"),
            (f"Set Model    --model", cfg.get(provider.upper()+"_MODEL","") or cfg.get("AI_MODEL","") or "auto"),
            (f"Set Preprompt --preprompt", (cfg.get("PREPROMPT","")[:30]+"..." if len(cfg.get("PREPROMPT",""))>30 else cfg.get("PREPROMPT","") or "empty")),
            (f"Set Log file --log", cfg.get("LOG","") or "empty"),
            (f"Set Rotate providers --rotate", cfg.get("AI_ROTATE_PROVIDERS","") or "empty"),
            (f"Set Search provider (exa/google)", cfg.get("SEARCH_PROVIDER","exa")),
            (f"Image out/height/width (pollinations)", ""),
            ("Back",""),
        ]
        pick=menu("CONFIG — tgpt config.conf", items)
        if pick is None or pick==10: break
        if pick==0:
            clear(); print(BOLD+f"CONFIG: {TGPT_CFG} (global) + ./config.conf (local, priority)"+RESET)
            if not TGPT_CFG.exists() and not TGPT_CFG_LOCAL.exists():
                print(c("no config file yet", YELLOW))
            else:
                for p in [TGPT_CFG, TGPT_CFG_LOCAL]:
                    if p.exists():
                        print(BOLD+f"\n--- {p} ---"+RESET)
                        print(p.read_text()[:3000])
            wait_enter()
        elif pick==1:
            editor=os.environ.get("EDITOR") or os.environ.get("VISUAL") or shutil.which("nano") or shutil.which("vi") or "vi"
            path=str(TGPT_CFG if not TGPT_CFG_LOCAL.exists() else TGPT_CFG_LOCAL)
            # Ensure file exists
            if not Path(path).exists():
                Path(path).parent.mkdir(parents=True, exist_ok=True)
                Path(path).touch()
            try: subprocess.call([editor, path])
            except Exception as e: print(c(f"failed {editor}: {e}", RED)); wait_enter()
        elif pick==2:
            k=text_input("API Key (AI_API_KEY or provider-specific like GROQ_API_KEY)")
            if k is not None: set_cfg_key("AI_API_KEY", k); print(c("AI_API_KEY updated", GREEN)); wait_enter()
        elif pick==3:
            u=text_input("URL (e.g. https://api.openai.com/v1 or http://localhost:11434/v1)", default=cfg.get("AI_URL",""))
            if u is not None: set_cfg_key("AI_URL", u); print(c(f"AI_URL={u}", GREEN)); wait_enter()
        elif pick==4:
            m=text_input("Model (e.g. gpt-4o-mini, deepseek-v4-flash-free)", default=cfg.get(provider.upper()+"_MODEL",""))
            if m:
                # store per provider
                if provider in PROVIDERS and PROVIDERS[provider][3]:
                    set_cfg_key(PROVIDERS[provider][3], m)
                else:
                    set_cfg_key("AI_MODEL", m)
                print(c("model updated", GREEN)); wait_enter()
        elif pick==5:
            pp=text_input("Preprompt (system prompt)", default=cfg.get("PREPROMPT",""))
            if pp is not None: set_cfg_key("PREPROMPT", pp); print(c("PREPROMPT updated", GREEN)); wait_enter()
        elif pick==6:
            lg=text_input("Log file path (--log)", default=cfg.get("LOG",""))
            if lg is not None: set_cfg_key("LOG", lg); wait_enter()
        elif pick==7:
            rot=text_input("Rotate providers comma-separated (e.g. deepseek,groq,anyapi,opencode)", default=cfg.get("AI_ROTATE_PROVIDERS",""))
            if rot is not None: set_cfg_key("AI_ROTATE_PROVIDERS", rot); print(c(f"AI_ROTATE_PROVIDERS={rot}", GREEN)); wait_enter()
        elif pick==8:
            sp=text_input("Search provider exa/google [exa]", default=cfg.get("SEARCH_PROVIDER","exa"))
            if sp: set_cfg_key("SEARCH_PROVIDER", sp); wait_enter()
        elif pick==9:
            print(BOLD+"Image options (pollinations only) — --out/--height/--width"+RESET)
            out=text_input("Default --out path", default=cfg.get("IMG_OUT",""))
            if out is not None: set_cfg_key("IMG_OUT", out)
            h=text_input("IMG height", default=cfg.get("IMG_HEIGHT",""))
            if h is not None: set_cfg_key("IMG_HEIGHT", h)
            w=text_input("IMG width", default=cfg.get("IMG_WIDTH",""))
            if w is not None: set_cfg_key("IMG_WIDTH", w)
            wait_enter()

def do_skills():
    # For tgpt, "skills" are loosely the roles/functions from shell_gpt, but we expose generic skill folder
    skills_dir = TGPT_DIR / "skills"
    if not skills_dir.exists():
        print(c(f"skills dir not found: {skills_dir}", YELLOW))
        print("tgpt doesn't have native skills, but you can add MCP servers as skills.")
        print("Create a skill as a prompt file in ~/.config/tgpt/skills/*.md")
        if text_input("Create skills folder now? (Y/n)", default="y").lower() in ("y","yes",""):
            skills_dir.mkdir(parents=True, exist_ok=True)
            (skills_dir / "example.md").write_text("# Example skill\nThis is a skill prompt you can use with tgpt --preprompt.\n")
            print(c(f"created {skills_dir}", GREEN))
        wait_enter()
        return
    files=sorted(skills_dir.glob("*.md")) + sorted(skills_dir.glob("*.txt"))
    if not files:
        print(c("no skills in "+str(skills_dir), YELLOW)); wait_enter(); return
    items=[(f.stem, "") for f in files]
    pick=menu("SKILLS — ~/.config/tgpt/skills", items)
    if pick is None: return
    try:
        data=files[pick].read_text()
        clear(); print(BOLD+files[pick].name+RESET); print(data[:4000])
    except Exception as e: print(c(f"error {e}", RED))
    # offer to use as preprompt
    if text_input("Use this skill as --preprompt? (y/N)", default="n").lower() in ("y","yes"):
        prompt=data[:2000]
        q=text_input("Your question for tgpt with this skill")
        if q: run_tgpt(["--preprompt", prompt, q])
    wait_enter()

def do_tools_quick():
    print(BOLD+"TOOLS QUICK — available built-in tools"+RESET)
    for tid,desc in TOOLS:
        print(f"  {tid:<22} {desc}")
    print("\nMCP tools are dynamic via --mcp-* (see MCP menu)")
    wait_enter()

MAIN_ITEMS = [
    ("Quick ask  (tgpt \"question\")", ""),
    ("Shell  (-s)  generate + execute", ""),
    ("Code   (-c)  generate code", ""),
    ("Find   (-f)  web search", ""),
    ("Interactive modes  (-i/-m/-is/-if/-ia)", ""),
    ("Image  (--img)  generate images", "pollinations/magicstudio/anyapi"),
    ("Tools  (-t)  built-in tools", "web_search, read_file, etc"),
    ("MCP  (--mcp)  Model Context Protocol", "filesystem, firecrawl..."),
    ("Provider selector  (--provider)", "free / free/api / paid"),
    ("Model selector  (--model)", ""),
    ("Config  (config.conf + keys/urls)", "AI_PROVIDER, keys, rotate..."),
    ("Skills  (~/.config/tgpt/skills)", ""),
    ("Show tools list", ""),
    ("Changelog  (tgpt --changelog)", ""),
    ("Updates locked (Android clipboard patch)", ""),
    ("Quit", ""),
]

def main_menu():
    while True:
        footer=DIM+f"provider={get_cfg('AI_PROVIDER','powerbrain')}  model={get_cfg(get_cfg('AI_PROVIDER','powerbrain').upper()+'_MODEL','') or get_cfg('OPENCODE_MODEL','') or get_cfg('AI_MODEL','auto')}  cfg={TGPT_CFG if TGPT_CFG.exists() else 'none'}"+RESET
        pick=menu("TGPT TOOLKIT — CONTROL CENTER", MAIN_ITEMS, footer=footer)
        if pick is None or pick==len(MAIN_ITEMS)-1: break
        if pick==0: do_quick_ask()
        elif pick==1: do_shell()
        elif pick==2: do_code()
        elif pick==3: do_find()
        elif pick==4: do_interactive_menu()
        elif pick==5: do_image()
        elif pick==6: do_tools()
        elif pick==7: do_mcp()
        elif pick==8: do_provider()
        elif pick==9: do_model()
        elif pick==10: do_config()
        elif pick==11: do_skills()
        elif pick==12: do_tools_quick()
        elif pick==13: clear(); run_tgpt(["--changelog"]); wait_enter()
        elif pick==14: clear(); print("Managed version is locked. Updates require a tested patch release from the software store."); wait_enter()

def main():
    args=sys.argv[1:]
    if args and args[0] in ("-h","--help"):
        print("tgpt-tui — terminal UI for tgpt (aandrew-me/tgpt)")
        print("")
        print("  no args            interactive TUI")
        print("  --ask '<q>'        quick ask")
        print("  --shell '<task>'   shell command")
        print("  --code '<task>'    code generation")
        print("  --find '<q>'       web search")
        print("  --img '<prompt>'   image generation")
        print("  --provider         provider selector")
        print("  --model            model selector")
        print("  --mcp              MCP menu")
        print("  --tools            tools selector")
        print("  --config           show config")
        print("  --preview          render main menu once")
        print("  --set-provider <id> set AI_PROVIDER")
        print("  --set-model <id>    set model for current provider")
        print("  --set-key <key>     set AI_API_KEY")
        return
    if args and args[0]=="--ask" and len(args)>1:
        clear(); run_tgpt([args[1]])
        return
    if args and args[0]=="--shell" and len(args)>1:
        clear(); run_tgpt(["-s", args[1]])
        return
    if args and args[0]=="--code" and len(args)>1:
        clear(); run_tgpt(["-c", args[1]])
        return
    if args and args[0]=="--find" and len(args)>1:
        clear(); run_tgpt(["-f", args[1]])
        return
    if args and args[0]=="--img" and len(args)>1:
        clear(); run_tgpt(["--img", args[1]])
        return
    if args and args[0]=="--provider": do_provider(); return
    if args and args[0]=="--model": do_model(); return
    if args and args[0]=="--mcp": do_mcp(); return
    if args and args[0]=="--tools": do_tools(); return
    if args and args[0]=="--config":
        for k,v in read_cfg().items():
            if "KEY" in k.upper(): print(f"{k}={v[:8]}...")
            else: print(f"{k}={v}")
        return
    if args and args[0]=="--set-provider" and len(args)>1:
        set_cfg_key("AI_PROVIDER", args[1]); print(f"AI_PROVIDER={args[1]}"); return
    if args and args[0]=="--set-model" and len(args)>1:
        prov=get_cfg("AI_PROVIDER","powerbrain")
        var=PROVIDERS.get(prov, (None,None,None,None))[3] if prov in PROVIDERS else None
        set_cfg_key(var or "AI_MODEL", args[1]); print(f"model {args[1]}"); return
    if args and args[0]=="--set-key" and len(args)>1:
        set_cfg_key("AI_API_KEY", args[1]); print("AI_API_KEY updated"); return
    if args and args[0]=="--preview":
        render("TGPT TOOLKIT — CONTROL CENTER", MAIN_ITEMS, 0, footer="")
        return
    main_menu()

if __name__=="__main__":
    try: main()
    except KeyboardInterrupt:
        clear(); print("bye"); sys.exit(0)

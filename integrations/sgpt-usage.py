import datetime, json, os, urllib.request

def resolve_cfg():
    here = os.path.dirname(os.path.abspath(__file__))
    sandbox = os.path.join(here, "..", "shell_gpt", ".sgptrc")
    if os.path.basename(os.path.dirname(here)) == ".gemini" and os.path.exists(sandbox):
        return sandbox
    return os.path.join(os.path.expanduser("~"), ".config", "shell_gpt", ".sgptrc")

CFG = resolve_cfg()
LIMIT = float(os.environ.get("SGPT_DAILY_NEURON_LIMIT", "10000"))

def cf_account_gateway():
    acc = os.environ.get("SGPT_CF_ACCOUNT", "")
    gw = os.environ.get("SGPT_CF_GATEWAY", "")
    if acc and gw:
        return acc, gw
    if os.path.exists(CFG):
        for line in open(CFG, encoding="utf-8", errors="ignore"):
            line = line.strip()
            if line.startswith("API_BASE_URL="):
                url = line.split("=", 1)[1].strip().rstrip("/")
                parts = url.split("/")
                if "gateway.ai.cloudflare.com" in url and len(parts) >= 6:
                    return parts[4], parts[5]
    return "", ""

ACCOUNT, GATEWAY = cf_account_gateway()

def token_from_cfg():
    if os.path.exists(CFG):
        for line in open(CFG, encoding="utf-8", errors="ignore"):
            line = line.strip()
            if line.startswith("OPENAI_API_KEY="):
                return line.split("=", 1)[1].strip()
    return os.environ.get("OPENAI_API_KEY", "")

def fetch_logs(token, page):
    url = ("https://api.cloudflare.com/client/v4/accounts/%s/ai-gateway/gateways/%s/logs?per_page=50&page=%d"
           % (ACCOUNT, GATEWAY, page))
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token, "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)

def main():
    if not ACCOUNT or not GATEWAY:
        print("Cloudflare usage tracking is disabled.")
        print("Set SGPT_CF_ACCOUNT and SGPT_CF_GATEWAY to enable it.")
        print("Config used:", CFG)
        return
    token = token_from_cfg()
    if not token:
        print("No OPENAI_API_KEY found in", CFG)
        return
    today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    total_neurons = 0.0
    total_cost = 0.0
    count = 0
    page = 1
    while page <= 15:
        data = fetch_logs(token, page)
        result = data.get("result", [])
        had_today = False
        for log in result:
            created = log.get("created_at", "") or ""
            if created[:10] == today:
                um = log.get("usage_metadata", {}) or {}
                total_neurons += float(um.get("neurons", 0))
                total_cost += float(log.get("cost", 0))
                count += 1
                had_today = True
        if not result or not had_today:
            break
        page += 1
    remain = LIMIT - total_neurons
    print("=" * 46)
    print("   GATEWAY USAGE / CONFIGURED LIMIT %d" % int(LIMIT))
    print("=" * 46)
    print("Date (UTC) :", today)
    print("Requests   :", count)
    print("Neurons    : %.2f" % total_neurons)
    print("Remaining  : %.2f" % remain)
    print("Est. cost  : $%.6f" % total_cost)
    print("Source     : AI Gateway logs (workers-ai)")

if __name__ == "__main__":
    main()

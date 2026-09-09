import re
import shutil
import subprocess

def fetch_tldr_and_flags(bin_name):
    examples = []
    flags = []

    # Query TLDR
    if shutil.which("tldr"):
        try:
            t_res = subprocess.run(["tldr", bin_name], capture_output=True, text=True, timeout=3)
            if t_res.returncode == 0:
                lines = t_res.stdout.splitlines()
                cur_desc = ""
                for line in lines:
                    sline = line.strip()
                    if not sline:
                        continue
                    if line.startswith("  - ") or (sline.endswith(":") and not line.startswith("    ")):
                        cur_desc = sline.lstrip("- ")
                    elif line.startswith("      ") or line.startswith("    "):
                        if not sline.startswith("<") and not sline.startswith("More info"):
                            examples.append({"desc": cur_desc, "cmd": sline})
                            for flg in re.findall(r'(?:--[a-zA-Z0-9_-]+|-[a-zA-Z0-9])', sline):
                                if flg not in flags:
                                    flags.append(flg)
        except Exception:
            pass

    # Extract common flags from --help if flags are few
    if len(flags) < 4 and shutil.which(bin_name):
        try:
            h_res = subprocess.run([bin_name, "--help"], capture_output=True, text=True, timeout=2)
            if h_res.returncode == 0:
                found = re.findall(r'(?:--[a-zA-Z0-9_-]+|-[a-zA-Z0-9])', h_res.stdout)
                for flg in found:
                    if flg not in flags and len(flg) <= 18:
                        flags.append(flg)
                        if len(flags) >= 12:
                            break
        except Exception:
            pass

    return examples, flags

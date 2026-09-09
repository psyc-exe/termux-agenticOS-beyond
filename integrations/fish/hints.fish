function helpme --description 'Practical command examples, with a local fallback'
    if test (count $argv) -eq 0
        printf 'software  Software store\napps      Installed apps\ntui       AI menus\nask       Natural-language chat\ntldr cmd  Practical examples\nerr -e "message"  Ask AI to explain an error\n'
        return
    end
    command tldr $argv
    or printf 'No cached examples. Try: %s --help  (refresh examples: tldr --update)\n' (string escape -- $argv[1])
end

function fish_command_not_found --description 'Local typo and package hints; never runs a correction'
    command python $AGENTICOS_ROOT/scripts/command-hint.py $argv[1]
    if test -x $PREFIX/libexec/termux/command-not-found
        $PREFIX/libexec/termux/command-not-found $argv[1]
    end
    printf 'Natural-language question? Enter ask to open chat.\n' >&2
    return 127
end

function __agenticos_postexec --on-event fish_postexec
    set -l result $status
    if test $result -ne 0; and test $result -ne 127; and test $result -ne 130
        set -l words (string split ' ' -- $argv[1])
        set -l cmd $words[1]
        printf 'Exit %s. Examples: helpme %s | Explain: err -e "paste the error"\n' $result (string escape -- $cmd) >&2
    end
    return $result
end

function err --description 'Explicit AI explanation or command drafting'
    if not command -qs tgpt; or not command -qs ask
        printf 'Enable tgpt in agenticos-software to use AI help. Local examples: tldr COMMAND\n'
        return 1
    end
    if test (count $argv) -lt 2
        printf 'err -e "error message" | err -s "task"\n'
        return 2
    end
    switch $argv[1]
        case -e --explain
            command ask "Explain this Termux/Fish error and suggest a fix: $argv[2..-1]"
        case -s --solve
            command tgpt -s "Termux/Fish task: $argv[2..-1]"
        case '*'
            printf 'Use -e to explain or -s to draft a command.\n'
            return 2
    end
end

function __agenticos_draft --description 'Draft a command on the input line; user reviews before Enter'
    command -qs tgpt; or return
    set -l prompt (commandline)
    test -n "$prompt"; or return
    set -l result (command tgpt -q -s -- "Termux/Fish command only, no explanation: $prompt")
    if test $status -eq 0; and test -n "$result"
        commandline -r -- (string join \n -- $result)
    end
    commandline -f repaint
end
bind \eg __agenticos_draft

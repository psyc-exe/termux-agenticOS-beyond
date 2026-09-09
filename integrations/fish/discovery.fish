function __agenticos_install --description 'Install and reveal newly available commands'
    set -l manager $argv[1]
    set -e argv[1]
    set -l before (mktemp)
    command python $AGENTICOS_ROOT/scripts/command-hint.py --snapshot > $before
    command $manager $argv
    set -l result $status
    if test $result -eq 0
        command python $AGENTICOS_ROOT/scripts/command-hint.py --new $before
    end
    command rm -f -- $before
    return $result
end

for manager in pkg apt npm bun
    # Runtime manager is derived from this function's name, never from eval.
    function $manager --inherit-variable manager --wraps $manager
        if test (count $argv) -gt 0; and contains -- $argv[1] install i add
            __agenticos_install $manager $argv
        else
            command $manager $argv
        end
    end
end

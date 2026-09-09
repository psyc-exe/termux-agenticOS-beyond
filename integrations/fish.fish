# Managed interactive profile; each store component is independently configurable.
status is-interactive; or return
fish_add_path --prepend --move --path $AGENTICOS_STATE/bin
set -l selected $HOME/.config/agenticos/fish-enabled
if test -f $selected
    for feature in (command cat $selected)
        switch $feature
            case aliases fuzzy hints discovery theme
                source $AGENTICOS_ROOT/integrations/fish/$feature.fish
        end
    end
end

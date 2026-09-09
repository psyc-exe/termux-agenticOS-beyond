set -g fish_color_error ff6e5e
set -g fish_color_command 5ea1ff
set -g fish_color_param c7cfff
set -g fish_color_autosuggestion 767f8d
if command -qs starship
    set -gx STARSHIP_CONFIG $HOME/.config/agenticos/starship.toml
    starship init fish | source
end

if command -qs fzf
    fzf --fish | source
end
if command -qs fd
    function fd --wraps fd
        command fd --hidden --no-ignore --color=auto $argv
    end
    alias fdh 'command fd --hidden --no-ignore --color=auto'
    alias fda 'command fd --hidden --no-ignore --absolute-path --color=auto'
    function ff --description 'Find files including dotfiles'
        command fd --hidden --no-ignore --color=never $argv | fzf --height 40% --reverse --preview 'bat --color=always --style=numbers --line-range=:100 {} 2>/dev/null'
    end
end

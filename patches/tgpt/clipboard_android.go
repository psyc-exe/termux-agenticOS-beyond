//go:build android

package clipboard

import (
	"encoding/base64"
	"fmt"
	"os"
)

// CopyToClipboard asks the terminal emulator to copy text via OSC 52.
// A standalone Termux process has no Android JVM clipboard context.
func CopyToClipboard(text string) {
	if len(text) > 65536 {
		fmt.Fprintln(os.Stderr, "Text too large for terminal clipboard; use terminal selection.")
		return
	}
	fmt.Printf("\x1b]52;c;%s\a", base64.StdEncoding.EncodeToString([]byte(text)))
	fmt.Fprintln(os.Stderr, "Clipboard request sent to terminal; use selection if unsupported.")
}

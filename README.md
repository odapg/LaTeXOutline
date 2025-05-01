## LaTeXOutline for Sublime Text

### Overview

LaTeXOutline is an ST4 package which allows displaying a clickable table of contents for a LaTeX file. This outline is shown on a separate tab.

LaTeXOutline is intended to be used with the `article`, `book` and `beamer` LaTeX classes.
In particular, the captured sectioning commands are: `part`, `chapter`, `section`, `subsection`, `subsubsection`, `subsubsubsection`, `paragraph` and `frametitle`.

![LaTeXOutline example](./images/example.png)

#### Manual installation

1. Clone or download this repository using the green `Clone or download` button.
2. If needed, rename the cloned or extracted folder to `LaTeXOutline`. 
3. Move the `LaTeXOutline` folder to your Sublime Text's `Packages` folder. 
4. Restart Sublime Text.
5. Modify the settings and possibly the `LaTeXOutline-custom.hidden-color-scheme` to your liking by going to the menu `Settings` > `Packages Settings`  > `LaTeXOutline`.

### Usage

1. Open a LaTeX File.
2. Use the command Palette entries `LaTeX Outline (Left)`, `LaTeX Outline (Right)` to open the outline pane and `LaTeX Outline: Close sidebar` to close it.
2. Alternatively, use the corresponding shortcuts (super j+a, super j+e, super j+z by default).
3. Click on the titles in the LaTeXOutline tab to get to the corresponding place in your LaTeX file.
3. Click on the *bullets* in the LaTeXOutline tab to copy the corresponding \label in the clipboard.
A message is given in the status bar below to indicate if this label has been found.

### License

This plugin is licensed under the MIT license. In particular, it is provided "as is", without warranty of any kind!

### Acknowledgements

LaTeXOutline is an adaptation to LaTeX projects of warmdev's original [SublimeOutline](https://github.com/warmdev/SublimeOutline). It also uses modifications due to vlad-wonderkidstudio's [SublimeOutline](https://github.com/vlad-wonderkidstudio/SublimeOutline).

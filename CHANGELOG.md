## LaTeXOutline for Sublime Text -- Changelog


#### Version 2.5

- The "take a look" view now opens in a panel (press `Esc` to close it).
- Adds an option in the settings for line-wrapping in the outline.
- Small fixes.


#### Version 2.4.3

- Now allows to limit the outline to sections/subsections and above (see the
  `.sublime-keymap` file).
- Refactored the "refresh after build" feature.


#### Version 2.4.2

- Bugfix (occasional numbering shift in presence of \section*).


#### Version 2.4.1

- Bugfix (incorrect outline updating when saving the .tex file).


#### Version 2.4

- Parses the `.out` file (when available, comes with `hyperref`) to present the final
  names of sections in the outline (when the `show_environments_names` is set to
  `true`).
- Changed the commands variables in the `sublime-keymaps` and `sublime-commands` files.
- The checks for section numbering have been relaxed to cover more cases.
- Bugfix (detected commented sections).


#### Version 2.3

- LaTeXOutline now accepts multiple-file documents.
- Internal modifications (LO no longer relies on ST's `symbols` list)


#### Version 2.2

- Gathers environment names (Theorem, Figure, etc.).
- Small corrections.


#### Version 2.1

- Adds a second outline containing the labels in addition to the table of contents.
- Adds two buttons (`❐` and `⌖`) to copy the label to the clipboard and to take a look to
  a part of the file without moving the caret.
- Adds section numbers and label references by parsing the .aux file (experimental).
- Now also considers \section*{...} etc.
- Corrects a bug occurring when two sections have the same name.
- Small corrections.


#### Version 2.0

- Adds the detection of `part`, `chapter`, `paragraph` and `frametitle` sectioning
  commands.
- Adds a `latexoutline.sublime-syntax` file, that, in particular, allows color
  highlighting of the LaTeXOutline tab.
- Correspondingly adds `.hidden-color-scheme` files to be used for that purpose.
- Adds the continuous synchronization of the location in the LaTeX file with the
  LaTeXOutline tab (only visible when the color highlighting is on.)
- Adds the possibility to copy the `label` corresponding to a section by clicking on the
  bullet.
- Simplification of the `sublime-settings` and `sublime-keymap` files.
- The commands `LaTeX Outline (Left)` or `(Right)` (and their corresponding shortcuts) now
  toggle the outline view (instead of just opening it).
- Clicking on a title in the outline should now bring to the correct place in the LaTeX
  file even if it has not been saved.
- The LaTeXOutline tab is now kept unchanged when activating a non-LaTeX file (such as
  a .log one).
- Important internal rewriting (but a substancial part of the code still comes from
  [SublimeOutline](https://github.com/warmdev/SublimeOutline) ).
- LaTeXOutline is now limited to ST4. 


#### Version 1.0

Initial release

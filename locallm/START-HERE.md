# Start here

**locallm trains a small language model on text you give it, on your own
computer.** Nothing is uploaded and nothing is sent anywhere: no account, no
key, no network. A model that was already trained comes with this copy, in the
`included-model` folder, so there is something to talk to before you train
anything of your own.

One warning first, because it is the thing people get wrong. The model that
comes with this copy learned formal program specifications, not English. Ask it
anything and it answers in that notation. Train your own on your own text and it
writes like your text instead.

You need Python already installed, version 3.10 or newer. If you have none, get
it from python.org.

## Start it

| Your computer | What to do |
|---|---|
| Linux | run `./start-linux.sh` in this folder |
| macOS | double-click `start-macos.command` |
| Windows | double-click `start-windows.bat` |

If your system blocks scripts, or double-clicking does nothing, open a terminal
or a command prompt in this folder and run:

    python3 home.py

That is the same program. On Windows, if `python3` is not found, use `py home.py`
instead: the installer from python.org provides the `py` command
(docs.python.org/3/using/windows.html).

## If it says: No module named 'tkinter'

This is the most common way this fails, and it is not your fault. The window is
drawn with Tk, and Python's own documentation calls `tkinter` an *optional*
module: a working Python can be missing it
(docs.python.org/3/library/tkinter.html). Installing it is one command.

- **Debian and Ubuntu**: `sudo apt install python3-tk`. On these systems it is a
  separate package that is not installed with `python3`
  (packages.debian.org/stable/python3-tk,
  launchpad.net/ubuntu/noble/+package/python3-tk).
- **Fedora**: `sudo dnf install python3-tkinter`. Same thing, different name
  (packages.fedoraproject.org/pkgs/python3.13/python3-tkinter/).
- **Another Linux**: search your package manager for `tkinter`. It is almost
  never packaged under that name alone.
- **macOS or Windows, Python from python.org**: nothing to do. The macOS
  installer says "A macOS-native version of Tk is included with the installer"
  (docs.python.org/3/using/mac.html), and the Windows installer installs Tcl/Tk
  and IDLE unless you turn that off (docs.python.org/3/using/windows.html).
- **macOS, Python from Homebrew**: Homebrew keeps Tk in a second package, one per
  Python version. Check yours with `python3 --version`, then install the match,
  for example `brew install python-tk@3.13`
  (formulae.brew.sh/formula/python-tk@3.13).
- **Windows, the "embeddable" zip**: that download deliberately contains no
  Tcl/Tk and no pip (docs.python.org/3/using/windows.html). Use the ordinary
  installer.

Everything in the next section that does not need the window still works while
you sort this out.

## What works with nothing else installed

| What you want | What it needs |
|---|---|
| talk to the model that came with this copy | Python alone |
| open the window and read it | Python and Tk |
| train on your own text | Python, Tk and PyTorch |

Talking to the included model needs only Python, because one file does it using
nothing but what Python already ships with (`plain_generate.py`). From this
folder:

    python3 plain_generate.py --out included-model --prompt "function to " --tokens 40

**It is slow, and slow is not broken.** Measured here on the included model: it
reads the model in under a tenth of a second, then writes one small piece of text
every 0.3 seconds or so (274 ms each over 40 pieces, 258 ms each over 25 on the
same machine). A short line therefore takes about ten seconds, and the text
appears all at once when it is finished, so wait for it.

**Training needs PyTorch**, which is a separate install:

    python3 -m pip install torch

Read that as a warning, not just a command. **It is a large download, roughly
2.5 GB**, which matters on a slow or metered connection far more than the install
itself does. The repository's `SHIPPING.md` has the measured size for each system.
Without PyTorch the window still opens and still explains itself, but the card
that trains and the card that reads a model both say plainly that they cannot
work yet.

## The first time

The window is four numbered cards, in order.

1. **Your text.** Drop a plain text file on it, or press Choose. Your notes, a
   book, a folder of code: anything whose contents are text.
2. **How big, how long.** Leave the slider at its smallest setting. Small and
   finished beats large and abandoned.
3. **Train.** Press Start training and numbers begin moving. Falling numbers mean
   it is learning the text. The card next to them says in one sentence what they
   mean, including when they do not yet mean anything.
4. **Try it.** Type a few words and it carries on from them.

Read the window rather than guessing at it. When something cannot work on your
machine, the card says which thing and why, in a sentence, instead of failing
quietly.

## The License

This is **not** free software and not open source, and calling it either would be
untrue. It is offered under a Research Use License: you may read it, run it,
change it and pass it on **for research and education only**, and explicitly not
as part of a product or a service, and not in production, without written
permission first. The full terms are in the `LICENSE` file beside this one. Read
it before you build anything on this. `NOTICE` beside it says who to ask if you
want to do more than research and education.

## What is in this folder

- `START-HERE.md`: this file.
- `home.py` and the Python files beside it: the program.
- `included-model/`: the model that came with this copy.
- `LICENSE` and `NOTICE`: the terms in full, and who to ask for anything wider.
- `MANIFEST.txt`: a sha256 and a byte count for every other file here, so a
  download that arrived damaged can be told from one that did not.

That is all of it. This folder is not the project, and the documents that carry
the evidence are not in this download: `README.md` for the tool in full,
`SHIPPING.md` for the measured sizes and timings behind the numbers above,
`ACHIEVEMENTS.md` for each result with its settings and hashes, `OFFLINE.md` for
what still works with no network, and one `FINDINGS-` file per question,
including the ones where the prediction turned out wrong. They live in the full
repository, together with the specification language the model was measured on,
the seven proof systems that check it, the problem corpora, the scoreboard and
the list of what is not claimed.

# Matsya client

Matsya is a service of Project Bellman. It reads an economist's description of a dynamic model, or a paper, writes the model in Bellman-SYM, the project's language for staged Bellman problems, checks what it wrote, and answers questions about models and about the language. This package installs the command `matsya`, through which you, or the coding assistant working for you, reach the service. Setting it up takes the four steps below, and the first two are done once.

## 1 Install the command

Open a terminal, the application in which you type commands (Terminal on a Mac, a shell on Linux, PowerShell on Windows), and type the following line, then press Enter:

```
pip install git+https://github.com/econ-ark/matsya
```

The installation needs Python 3.10 or newer and nothing else, and it ends with a line saying that `econ-ark-matsya` was installed. If your system's Python refuses to install packages, the message says so, type `pipx install git+https://github.com/econ-ark/matsya` instead, which gives the command an environment of its own. Afterwards, typing `matsya --help` prints the list of commands, which shows that the installation worked.

## 2 Enter your Matsya token

The service knows you by a **Matsya token**, a string of letters and digits beginning `msy_`, which the service's administrator sends you by private message together with the service's address. In the same terminal, type

```
matsya configure
```

and press Enter. The command asks first for the Matsya token and then for the address; paste each and press Enter. Both are saved in a private file in your home folder, and neither is printed again. To confirm that the service accepts you, type `matsya index`: it prints the name of the index the service reads and the version of its configuration. If it prints a refusal instead, the token or the address was mistyped, and `matsya configure` lets you enter them again.

## 3 Let your assistant work with Matsya

Most of the work is done for you by a coding assistant such as Claude Code. Open the folder that holds your model's description in the assistant, and tell it, in your own words, to read the Matsya user guide and to use the `matsya` command for you. The guide is at <https://econ-ark.github.io/bellman/matsya/user-guide/>, and the same pages are installed with the command and stand in the folder `docs/` of this repository; they tell the assistant what Matsya does, which commands exist, what each prints, and where the files it writes are kept. From then on you describe what you want, a declaration built from your description, a question about the result, a change to the model, and the assistant runs the commands.

## 4 Or run the commands yourself

Every command is also meant to be typed by hand. `matsya --help` lists them, and the user guide explains each with what it prints. The three you will use most are `matsya job submit model.md`, which has the model described in the file built and checked, `matsya job wait <job>`, which follows that work to its end, and `matsya ask <session> "your question"`, which asks a question about a model in the session the first command created.

## Source and license

The client is developed in the folder `AI/matsya-acess/client/` of the Bellman project's repository and published here; its version is the one in `pyproject.toml`, tagged at each release. This repository first held an earlier client of the previous Matsya service, whose last commit was `6b1bf86`, under the Apache 2.0 license retained in [LICENSE](LICENSE); the present code calls the routes of the Matsya service of spec 0.3 and no other service.

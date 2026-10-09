# Matsya client

Matsya is a service of Project Bellman. It reads an economist's description of a dynamic model, or a paper, writes the model in Bellman-SYM, the project's language for staged Bellman problems, checks what it wrote, and answers questions about models and about the language.  Matsya contains a curated corpus of theoretical and applied knowledge of dynamic programming and skills to communicate that knowledge for the purpose of helping economists develop dynamic models. 

This package installs the command `matsya`, through which you, or the coding assistant working for you, reach the service. Setting it up takes the four steps below, and the first two are done once.

## 1 Install the command

Open a terminal, the application in which you type commands (Terminal on a Mac, a shell on Linux, PowerShell on Windows), and type the following line, then press Enter:

```
pip install git+https://github.com/econ-ark/matsya
```

The installation needs Python 3.10 or newer and nothing else, and it ends with a line saying that `econ-ark-matsya` was installed. If your system's Python refuses to install packages, the message says so, type `pipx install git+https://github.com/econ-ark/matsya` instead, which gives the command an environment of its own. Afterwards, typing `matsya --help` prints the list of commands, which shows that the installation worked.

## 2 Enter your Matsya token

The service knows you by a **Matsya token**, a string of letters and digits beginning `msy_`, which the service's administrator sends you by private message together with the service's **address**, a line beginning `http://` or `https://`. Have both at hand, because the next command asks for them one after the other. In the terminal, type

```
matsya configure
```

and press Enter. The command first prints its title line,

```
Matsya: save your Matsya token and the service address
```

and then asks for the token:

```
Enter your Matsya token:
```

Paste the Matsya token after the colon, exactly as you received it, and press Enter. If what you pasted does not begin with `msy_`, the command stops with the sentence `Error: a Matsya token begins with msy_. Check the Matsya token you received and try again.`, and you type `matsya configure` once more. Otherwise it asks for the address:

```
Enter the service address supplied by AAS:
```

Paste the address and press Enter. The command then prints where it saved the two,

```
Matsya token and service address saved to /Users/you/.config/matsya/config.toml
```

with your own home folder in place of `/Users/you`, followed by the reminder that the service keeps the entries of your sessions and the records of your jobs, and the line `Check your access with: matsya index`. The two values are saved in that private file only and are never printed again; the token is shown on the screen while you paste it, so paste it where no one is looking over your shoulder.

To check, type `matsya index` and press Enter. When the service accepts you, it prints three lines: the name of the index the service reads, the embedding model, and the configuration's version. When it does not, it prints one line beginning `Error: The service refused the request (401)`, which means the token was mistyped or is not known to the service, or a line saying that the connection failed, which means the address was mistyped or the service is unreachable; in either case type `matsya configure` again and enter the values once more.

## 3 Let your assistant work with Matsya

Most of the work is done for you by a coding assistant such as Claude Code. Open the folder that holds your model's description in the assistant, and tell it, in your own words, to read the Matsya user guide and to use the `matsya` command for you. The guide is at <https://econ-ark.github.io/bellman/matsya/user-guide/>, and the same pages are installed with the command and stand in the folder `docs/` of this repository; they tell the assistant what Matsya does, which commands exist, what each prints, and where the files it writes are kept. Typed alone, `matsya` prints an orientation, which says what Matsya is, where the guide is installed on your machine and whether your Matsya token is saved, and `matsya docs` prints the guide itself. From then on you describe what you want, a declaration built from your description, a question about the result, a change to the model, and the assistant runs the commands.

## 4 Or run the commands yourself

Every command is also meant to be typed by hand. `matsya --help` lists them, and the user guide explains each with what it prints. The three you will use most are `matsya job submit model.md`, which has the model described in the file built and checked, `matsya job wait <job>`, which follows that work to its end, and `matsya ask <session> "your question"`, which asks a question about a model in the session the first command created.

## Source and license

The client is developed in the folder `AI/matsya-acess/client/` of the Bellman project's repository and published here; its version is the one in `pyproject.toml`, tagged at each release. This repository first held an earlier client of the previous Matsya service, whose last commit was `6b1bf86`, under the Apache 2.0 license retained in [LICENSE](LICENSE); the present code calls the routes of the Matsya service of spec 0.3 and no other service.

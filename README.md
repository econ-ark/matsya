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
Enter the service address supplied by Econ-ARK-admin:
```

Paste the address and press Enter. The command then prints where it saved the two,

```
Matsya token and service address saved to /Users/you/.config/matsya/config.toml
```

with your own home folder in place of `/Users/you`, followed by the reminder that the service keeps the entries of your sessions and the records of your jobs, and the line `Check your access with: matsya index`. The two values are saved in that private file only and are never printed again; the token is shown on the screen while you paste it, so paste it where no one is looking over your shoulder.

To check, type `matsya index` and press Enter. When the service accepts you, it prints three lines: the name of the index the service reads, the embedding model, and the configuration's version. When it does not, it prints one line beginning `Error: The service refused the request (401)`, which means the token was mistyped or is not known to the service, or a line saying that the connection failed, which means the address was mistyped or the service is unreachable; in either case type `matsya configure` again and enter the values once more.

## 3 Let your assistant work with Matsya

You do not need to learn the commands. A coding assistant such as Claude Code runs them for you, and Matsya tells the assistant how: typed alone, `matsya` answers with where its guide is and how to read it. So instruct your assistant to ask Matsya how to read its instructions.

In Claude Code, open the folder that holds your model's description and type at its prompt:

```
Ask matsya how it works, read its instructions, and then use the matsya command for me.
```

Claude Code runs `matsya`, which points it to the guide; it reads the guide with `matsya docs --all`; and it is then ready. From then on, say what you want in your own words. For example:

```
Build the model described in economics.md.
```

Claude Code runs `matsya job submit economics.md`, follows the job to its end, and reports the job's label, its outcome and the architect's questions if it has any.

```
What did the two judges disagree on in that job?
```

Claude Code runs `matsya ask` in the session the job created and shows you the answer with its citations.

```
Answer the architect's first question: the gross return on assets is R, and assets cannot be negative.
```

Claude Code appends your answer to the session as the reply to that question, which starts the next job, and follows it.

The guide the assistant reads is installed with the command; it is also online at <https://econ-ark.github.io/bellman/matsya/user-guide/>.

## 4 Or run the commands yourself

Every command is also meant to be typed by hand. `matsya --help` lists them, and the user guide explains each with what it prints. The three you will use most are `matsya job submit model.md`, which has the model described in the file built and checked, `matsya job wait <job>`, which follows that work to its end, and `matsya ask <session> "your question"`, which asks a question about a model in the session the first command created.

## Source and license

The client is developed in the folder `AI/matsya-acess/client/` of the Bellman project's repository and published here; its version is the one in `pyproject.toml`, tagged at each release. This repository first held an earlier client of the previous Matsya service, whose last commit was `6b1bf86`, under the Apache 2.0 license retained in [LICENSE](LICENSE); the present code calls the routes of the Matsya service of spec 0.3 and no other service.

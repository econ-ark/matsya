# Matsya client

Matsya reads an economist's description of a dynamic model, or a paper, writes the model in Bellman-SYM, the language of staged Bellman problems of Project Bellman, checks what it wrote, and answers questions about models and about the language. This package is the command `matsya`, through which you, or the coding assistant working for you, reach the service. Four steps:

1. **Install.** `pip install git+https://github.com/econ-ark/matsya`, or `pipx install git+https://github.com/econ-ark/matsya` for a command with an environment of its own. Python 3.10 or newer, nothing else.

2. **Enter your Matsya token.** The service's administrator sends you, by private message, a Matsya token, a string beginning `msy_` that identifies you to the service, and the service's address. Run `matsya configure` once and paste both; they are saved in a private file in your home folder and are never printed. `matsya index` then confirms that the service accepts you.

3. **Point your assistant to the guide.** Open the folder of your model with your coding assistant, Claude Code or another, and tell it to read the Matsya user guide at <https://econ-ark.github.io/bellman/matsya/user-guide/> and to use the `matsya` command. The guide says what Matsya does, which commands exist and what each prints, and where the local files live, so that the assistant runs the commands for you; the same pages stand in this repository's `docs/` folder and are installed with the package.

4. **Or run the commands yourself.** `matsya --help` lists them; the guide explains them.

## Source and license

The client is developed in the folder `AI/matsya-acess/client/` of the Bellman project's repository and published here; its version is the one in `pyproject.toml`, tagged at each release. This repository first held an earlier client of the previous Matsya service, whose last commit was `6b1bf86`, under the Apache 2.0 license retained in [LICENSE](LICENSE); the present code calls the routes of the Matsya service of spec 0.3 and no other service.

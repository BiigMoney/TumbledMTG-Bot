## TumbledMTG

The official discord bot of the TumbledMTG custom Magic: the Gathering format, currently going by TumbledMTG-Bot#3906.

## How to Run

Make sure [Python](https://www.python.org/) and [Pip](https://pypi.org/project/pip/) are installed on your system.

First, create and configure a new [Discord app](https://discord.com/developers/docs/getting-started#creating-an-app).

Next, clone and cd into this repository and create a virtual environment by running `python -m venv venv`. Once you have created your virtual environment, [activate](https://docs.python.org/3/tutorial/venv.html#creating-virtual-environments) it and run `pip install -r requirements.txt`.

If you want the bot to show TumbledMTG cards, run `git clone https://github.com/OKThomas1/TumbledMTG-Cockatrice.git` inside your clone of this repository, otherwise you will have to remove the `clone()` function and rewrite how the bot fetches cards.

Finally, create a .env file and set the required environment variables (see [.env.example](.env.example)), and run the bot with `python bot.py`.

## Contributing

If you are interesting in contributing, join the [TumbledMTG Discord](https://discord.gg/2G4n5bgPgY) and contact Tumbles#3232 or Big Money#7196.

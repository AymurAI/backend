# Contributing to AymurAI

We are happy to accept your contributions to make `AymurAI` better and more awesome! To avoid unnecessary work on either
side, please stick to the following process:

1. Check if there is already [an issue](https://github.com/AymurAI/dev/issues) for your concern.
2. If there is not, open a new one to start a discussion. We hate to close finished PRs!
3. If we decide your concern needs code changes, we would be happy to accept a pull request. Please consider the
commit guidelines below.

In case you just want to help out and don't know where to start,
[issues with "help wanted" label](https://github.com/AymurAI/dev/labels/help%20wanted) are good for
first-time contributors.



## Developing locally

For contributors looking to get deeper into the API we suggest cloning the repository.
Nearly all classes and methods are documented, so finding your way around
the code should hopefully be easy.

### Setup

#### Using Docker and devcontainer (recommended)
You can use the provided `devcontainer` load all the tools and packages needed. This can be done directly from Visual Studio Code.
You can check the [devcontainer documentation](https://code.visualstudio.com/docs/remote/containers) for more information.

#### Using jupyterlab image
If you want just check the notebooks and tutorials you can use the `jupyterlab` docker image. To run the image in `gpu` mode run:
```bash
make jupyter-run
```
alternatively you can run in `cpu` mode with:
```bash
make jupyter-run-cpu
```


#### Install direclty on a your python environment
create a python environment of your preference and run:
```bash
pip install src/aymurai
```

You may need to install redis or run it in a docker container. You can use the following command to run it in a docker container:
```bash
make redis-run
```

### Git pre-commit Hooks
After installing the dependencies, install `pre-commit` hooks via:
```bash
pre-commit install
```

This will automatically run code formatters black and isort for each git commit. Also it will clear all outputs from the notebooks. If you want to more information about why we do this, please refer to the [data security](docs/DATA_SECURITY.md) section.


### Code Formatting

To ensure a standardized code style we use the formatter [black](https://github.com/ambv/black) and for standardizing imports we use [isort](https://github.com/PyCQA/isort).
If your code is not formatted properly, the tests will fail.

If you set up pre-commit hooks, every git commit will automatically run these formatters. Otherwise you can also manually run them, or let your IDE run them on every file save.
Running from the command line works via `black src/aymurai/ && isort src/aymurai/` in the repository root folder.

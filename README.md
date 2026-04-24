# AymurAI Desktop App

## Technologies

### Main technologies

- ⚛️ **React** + 🆎 **TypeScript** as the _main framework_ with _type checking_
tools
- ⚡ **Electron** as the _deployment and packaging tool_. It also serves the
purpose of communicating the webapp with the _NodeJS_ process.
- 🪡 **Stitches** as the _styling library_
- 🛣️ **Tanstack React Router** as the _routing library_ to navigate across the webapp
- 📄 **Mammoth** + **ExcelJS** as the _libraries_ to read and write `.docx` and
datasheet files

### Other technologies

- **pnpm** as _package manager_
- **biome** as code _linter and formatter_

##  Getting started

1. Clone the repository

1. Navigate to the repository folder and install dependencies with

    ```bash
    pnpm install
    ```

1. Start the app in development mode with

   ```bash
   pnpm run dev
   ```

## Run Aymurai API

1. First download the image

    ```sh
    docker pull registry.gitlab.com/collective.ai/datagenero-public/aymurai-api-prod
    ```

2. And then create the corresponding container

    ```sh
    docker run -p 8899:8899 -h -d registry.gitlab.com/collective.ai/datagenero-public/aymurai-api-prod:latest
    ```

## Scripts

### Development

- `dev:web`: starts the frontend locally to be viewed in a conventional browser
- `dev`: starts the frontend locally and creates an _Electron_ instance to view it
- `start`: previews the production build with Electron
- `start:web`: previews the production web build in a browser

### Build

- `build:web`: builds the React Vite project
- `build`: builds both React and Electron projects (without packaging the application)

### Validation

- `lint`: runs the linter (_Biome_) across the entire project
- `lint:fix`: fixes linter errors automatically
- `format`: checks code formatting with _Biome_
- `format:fix`: fixes code formatting automatically
- `typecheck`: runs type checking on both _Node_ and _Web_ applications
- `typecheck:node`: runs type checking on the _Electron_ application
- `typecheck:web`: runs type checking on the _React_ application
- `validate`: runs linting and type checking on both React and renderer
- `pre-commit`: runs _LintStaged_

### Deployment

- `build:unpack`: builds and creates an unpacked distribution directory
- `build:[win|mac|linux]`: builds and packages the application for the desired target
- `package`: cleans build directory, builds, and packages the app with Electron Forge
- `make`: cleans build directory, builds, and creates distributables with Electron Forge
- `postinstall`: installs app dependencies for Electron Builder

##  Colaborators

- Melina Gatto (_Project Manager_)
- Luciana Vega (_Project Manager_)
- Andy Orlandi (_Product Designer_)
- Luciano Lapenna (_Developer_)
- Ender Puentes (_Developer_)

## Special thanks

- Lucia Wainfeld

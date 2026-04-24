/**
 * Interface for the filesystem preloaded script on the main process
 * @returns FileSystem functionalities
 */
export default function filesystemAPI() {
  if (window.filesystem) {
    return window.filesystem;
  }

  throw new Error(
    'There was an error trying to use the "filesystem" API, check your preload script',
  );
}

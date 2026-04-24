/**
 * Interface for the taskbar API
 * @returns Taskbar functionalities
 */
export default function taskbar() {
  if (window.taskbar) return window.taskbar;

  throw new Error(
    'There was an error trying to use the "taskbar" API, check your preload script',
  );
}

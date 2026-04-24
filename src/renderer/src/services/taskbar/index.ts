import taskbarAPI from "./utils";

/**
 * Notify the user with a sound and an action on the taskbar/dock
 */
function notify() {
  taskbarAPI().notify();
  const audio = new Audio("audio/notification.mp3");
  audio.play();
}

const taskbar = {
  notify,
};

export default taskbar;

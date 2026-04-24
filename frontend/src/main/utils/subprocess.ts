import { exec, spawn } from "node:child_process";
import path from "node:path";
import { app } from "electron";

export const run = () => {
  const batFilePath = path.join(app.getPath("exe"), "../run_server.bat");
  const child = spawn(batFilePath);

  return new Promise((ok, no) => {
    if (!child) return no(new Error("Child process not found"));

    child.on("spawn", () => {
      ok(true);
    });
    child.on("error", (err) => {
      no(err);
    });
  });
};

export const stop = (): Promise<boolean> => {
  return new Promise((ok, no) => {
    exec(
      'powershell "& Get-Process -Name python | ? { $_.Path -eq \\"$env:USERPROFILE\\miniconda3\\envs\\aymurai-backend\\python.exe\\"} | Stop-Process"',
      (err) => {
        if (err) return no(err);
        ok(true);
      },
    );
  });
};

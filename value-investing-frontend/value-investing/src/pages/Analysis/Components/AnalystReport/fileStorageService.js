import localforage from "localforage";

const STORAGE_KEY = "analyst_report_staged_files";

export async function loadStagedFiles() {
  const files = await localforage.getItem(STORAGE_KEY);
  return files ?? [];
}

export async function saveStagedFiles(files) {
  await localforage.setItem(STORAGE_KEY, files);
}

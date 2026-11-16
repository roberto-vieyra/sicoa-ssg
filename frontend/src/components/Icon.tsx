const paths: Record<string, string> = {
  inbox: "M4 4h16v16H4z M4 13h5l2 3h2l2-3h5",
  search: "M20 20l-5-5 M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0",
  plus: "M12 5v14 M5 12h14",
  arrow: "M9 5l7 7-7 7",
  download: "M12 3v12 M7 10l5 5 5-5 M4 16v5h16v-5",
  clock: "M12 8v5l3 2 M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0",
  check: "M5 12l4 4L19 6",
  alert: "M12 3L2 21h20L12 3z M12 9v5 M12 17v1",
  users:
    "M16 21v-3a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v3 M13 6a4 4 0 1 1-8 0 4 4 0 0 1 8 0 M18 3a4 4 0 0 1 0 8 M22 21v-3a4 4 0 0 0-3-3.8",
  file: "M14 2H4v20h16V8l-6-6z M14 2v6h6 M8 13h8 M8 17h5",
  exit: "M9 4H3v16h6 M9 12h12 M16 7l5 5-5 5",
  close: "M6 6l12 12 M6 18L18 6",
  history: "M3 11a9 9 0 1 1 2 7 M3 4v7h7 M12 7v6l4 2",
  shield: "M12 2l9 4v6c0 5-9 10-9 10S3 17 3 12V6l9-4z M8 11l3 3 5-5",
};
export function Icon({ name, size = 18 }: { name: string; size?: number }) {
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={paths[name] || paths.file} />
    </svg>
  );
}

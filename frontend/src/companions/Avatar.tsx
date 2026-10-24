import type { BotId } from "./registry";
import { botById } from "./registry";

export function BotAvatar({ id, size = 56 }: { id: BotId; size?: number }) {
  return (
    <span
      className="bot-avatar"
      style={{ width: size, height: size, background: botById(id)!.color }}
      aria-hidden="true"
    >
      <svg viewBox="0 0 80 80" fill="none">
        {id === "may" && (
          <>
            <path
              d="M17 48c-10-5-7-21 4-22 2-14 23-17 29-4 13-4 22 10 15 20 8 15-8 26-19 18-10 8-27 2-29-12Z"
              fill="#87b8a2"
            />
            <path
              d="M22 46c-7-5-3-16 5-16 3-11 18-11 22-1 11-3 17 9 11 16 6 10-6 16-14 11-9 5-23 1-24-10Z"
              fill="#b6d6be"
            />
            <path
              d="M32 40v3m16-3v3m-12 6q4 4 8 0"
              stroke="#285647"
              strokeWidth="2.5"
              strokeLinecap="round"
            />
            <ellipse cx="27" cy="47" rx="3" ry="2" fill="#e5b2a0" />
            <ellipse cx="53" cy="47" rx="3" ry="2" fill="#e5b2a0" />
          </>
        )}
        {id === "guong" && (
          <>
            <rect
              x="18"
              y="12"
              width="44"
              height="56"
              rx="21"
              fill="#b3a0d7"
              transform="rotate(-9 40 40)"
            />
            <rect
              x="24"
              y="18"
              width="32"
              height="44"
              rx="16"
              fill="#e1d6f2"
              transform="rotate(-9 40 40)"
            />
            <path
              d="m28 28 7-5m-3 15v4m16-7v4m-13 8q5 4 10-2"
              stroke="#625080"
              strokeWidth="2.5"
              strokeLinecap="round"
            />
            <path d="m62 15 2 5 5 2-5 2-2 5-2-5-5-2 5-2Z" fill="#8e76b7" />
          </>
        )}
        {id === "nhip" && (
          <>
            <path
              d="m40 10 6 9 11-1 2 11 10 5-6 10 2 11-11 3-7 10-9-6-12 3-4-11-10-5 5-10-2-12 11-3 6-11Z"
              fill="#e9b75a"
            />
            <circle cx="40" cy="40" r="21" fill="#ffe6a1" />
            <path
              d="M31 37v4m17-4v4m-14 5q6 8 12-1"
              stroke="#835519"
              strokeWidth="2.7"
              strokeLinecap="round"
            />
          </>
        )}
        {id === "rure" && (
          <>
            <path
              d="m40 10 9 15 17 1-7 17 5 17-19 1-13 11-7-18-16-9 12-13 2-18 17 5Z"
              fill="#e79476"
            />
            <path
              d="m40 21 6 11 12 1-6 12 2 11-12-3-10 8-5-12-10-6 10-9 2-12 11 5Z"
              fill="#ffc5a6"
            />
            <path
              d="m31 36 4 2-4 2m17-4v4m-11 6q4 4 8-1"
              stroke="#8e4938"
              strokeWidth="2.4"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </>
        )}
        {id === "caunoi" && (
          <>
            <path
              d="M15 44c0-25 50-25 50 0v13H53V44c0-12-26-12-26 0v13H15Z"
              fill="#7bafcd"
            />
            <path
              d="M24 45c0-17 32-17 32 0v12H45V45c0-4-10-4-10 0v12H24Z"
              fill="#b2d8e8"
            />
            <path
              d="M31 32v3m17-3v3m-13 6q5 4 10 0"
              stroke="#365f78"
              strokeWidth="2.4"
              strokeLinecap="round"
            />
            <circle cx="20" cy="58" r="7" fill="#a0c8d8" />
            <circle cx="59" cy="58" r="7" fill="#a0c8d8" />
          </>
        )}
      </svg>
    </span>
  );
}

export function BrandMark() {
  return (
    <svg
      viewBox="0 0 40 40"
      width="34"
      height="34"
      fill="none"
      aria-hidden="true"
    >
      <rect width="40" height="40" rx="13" fill="#285c4b" />
      <path
        d="M9 25V16c0-4 7-4 7 0v9m0-7c0-5 8-5 8 0v7m0-9c0-4 7-4 7 0v9"
        stroke="#f3f4de"
        strokeWidth="3"
        strokeLinecap="round"
      />
      <circle cx="30" cy="10" r="3" fill="#e9b75a" />
    </svg>
  );
}

export type BotId = "may" | "guong" | "nhip" | "rure" | "caunoi";
export type InlineCard =
  | { kind: "mood"; value?: number }
  | { kind: "insight" }
  | { kind: "profile"; text: string; decision?: "saved" | "skipped" }
  | { kind: "activity"; mode: "puzzle" | "learn"; revealed?: boolean }
  | { kind: "match" }
  | { kind: "handoff"; botId: BotId };
export type BotMessage = {
  id: string;
  actor: "self" | "bot";
  text: string;
  card?: InlineCard;
};
export type BotThread = {
  messages: BotMessage[];
  turn: number;
  pending?: string;
  lastInput: string;
  error: boolean;
  unread: boolean;
};
export type BotProfile = {
  id: BotId;
  name: string;
  role: string;
  description: string;
  color: string;
  intro: string;
  starters: string[];
};
export const bots: BotProfile[] = [
  {
    id: "may",
    name: "Mây",
    role: "Lắng nghe & tâm sự",
    description: "Một khoảng nhỏ để được lắng nghe.",
    color: "#dfebe5",
    intro:
      "Có gì muốn kể mình nghe không? Một ngày dài hay một niềm vui bé xíu cũng được.",
    starters: ["Hôm nay mình hơi mệt", "Kể một chút", "Đổi chủ đề"],
  },
  {
    id: "guong",
    name: "Gương",
    role: "Khám phá bản thân",
    description: "Tìm thêm một điều thú vị về bạn.",
    color: "#ebe4f6",
    intro: "Có điều gì bạn làm mãi mà không thấy chán không?",
    starters: [
      "Mình thích đọc sách",
      "Mình thích khám phá điều mới",
      "Điều mình coi trọng",
    ],
  },
  {
    id: "nhip",
    name: "Nhịp",
    role: "Cảm xúc & thói quen",
    description: "Chậm một nhịp, nghe mình một chút.",
    color: "#f9e5bd",
    intro: "Hôm nay bạn thấy thế nào? Chọn cảm giác gần với bạn nhất nhé.",
    starters: ["Ghi lại cảm xúc", "Nhìn lại tuần", "Một thói quen nhỏ"],
  },
  {
    id: "rure",
    name: "Rủ Rê",
    role: "Học hỏi & cùng chơi",
    description: "Thử một điều mới, vui thêm một chút.",
    color: "#f9ded3",
    intro: "Có ba phút rảnh không? Mình có một vài ý tưởng hay ho đây!",
    starters: ["Giải đố", "Học gì đó", "Tìm người chơi cùng"],
  },
  {
    id: "caunoi",
    name: "Cầu Nối",
    role: "Tìm bạn đồng điệu",
    description: "Từ một điểm chung đến một người bạn.",
    color: "#dcebf5",
    intro: "Bạn muốn tìm người cùng học, cùng chơi hay cùng chia sẻ sở thích?",
    starters: [
      "Tìm bạn cùng sở thích",
      "Cùng học tiếng Anh",
      "Sửa hồ sơ kết nối",
    ],
  },
];
export const botById = (id?: string) => bots.find((b) => b.id === id);
export function initialThreads(): Record<BotId, BotThread> {
  return Object.fromEntries(
    bots.map((b) => [
      b.id,
      {
        messages: [
          {
            id: `${b.id}-intro`,
            actor: "bot",
            text: b.intro,
            ...(b.id === "nhip" ? { card: { kind: "mood" } } : {}),
          },
        ],
        turn: 0,
        lastInput: "",
        error: false,
        unread: false,
      },
    ]),
  ) as Record<BotId, BotThread>;
}

export type LegacyBotId = "may" | "guong" | "nhip" | "rure" | "caunoi";
/** V3 default agents (AI_THREE_AGENT_EXPERIENCE_ENABLED). */
export type AgentId = "dieuphoi" | "nhatky" | "hoatdong";
export type BotId = LegacyBotId | AgentId;
export const AGENT_IDS: readonly AgentId[] = ["dieuphoi", "nhatky", "hoatdong"];
export const isAgentId = (id: unknown): id is AgentId =>
  typeof id === "string" && (AGENT_IDS as readonly string[]).includes(id);
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
      "Sửa hồ sơ tìm bạn",
    ],
  },
];
/** V3 agents. Only their own descriptions; legacy companions above stay for history labels. */
export const agents: BotProfile[] = [
  {
    id: "dieuphoi",
    name: "Điều phối",
    role: "Trò chuyện & lên hướng đi",
    description: "Hiểu điều bạn cần, cùng bạn gỡ rối và gọi đúng người giúp.",
    color: "#d9ebe3",
    intro: "Hôm nay bạn muốn trò chuyện, gỡ rối một việc hay sắp xếp kế hoạch? Cứ kể mình nghe.",
    starters: ["Hôm nay mình hơi rối", "Giúp mình sắp xếp tuần này", "Mình muốn hiểu bản thân hơn"],
  },
  {
    id: "nhatky",
    name: "Nhật ký",
    role: "Nhật ký & cảm xúc",
    description: "Nhìn lại những gì bạn đã ghi, nhận ra điều lặp lại.",
    color: "#f8e6bf",
    intro: "Muốn nhìn lại vài ngày qua, hay viết thêm vài dòng cho hôm nay?",
    starters: ["Nhìn lại tuần này", "Giúp mình viết vài dòng", "Một thói quen nhỏ"],
  },
  {
    id: "hoatdong",
    name: "Hoạt động",
    role: "Hoạt động & học hỏi",
    description: "Biến ý định thành một việc nhỏ làm được ngay.",
    color: "#fbdccf",
    intro: "Có chút thời gian rảnh không? Mình gợi ý một việc nhỏ làm được ngay nhé.",
    starters: ["Gợi ý việc nhẹ cho tối nay", "Mình muốn học điều mới", "Chia nhỏ mục tiêu giúp mình"],
  },
];
const allProfiles = [...bots, ...agents];
export const botById = (id?: string) => allProfiles.find((b) => b.id === id);
export function initialThreads(): Record<BotId, BotThread> {
  return Object.fromEntries(
    allProfiles.map((b) => [
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

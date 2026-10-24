import { initialThreads } from "../companions/registry";
import type { Candidate, Profile, State } from "../domain/types";
export const interests = {
  reading: "Đọc sách",
  music: "Nghe nhạc",
  walking: "Đi bộ",
  cooking: "Nấu ăn",
  english: "Học tiếng Anh",
  photography: "Chụp ảnh",
  puzzles: "Giải đố",
};
export const values = {
  respect: "Tôn trọng",
  sincerity: "Chân thành",
  curiosity: "Ham học hỏi",
  kindness: "Tử tế",
};
export const styles = {
  balanced: "Cân bằng",
  listening: "Thích lắng nghe",
  direct: "Thích nói thẳng",
};
export const goals = {
  "shared-interests": "Tìm bạn cùng sở thích / cùng học",
  friendship: "Tìm bạn trò chuyện",
};
export const languages = { vi: "Tiếng Việt", en: "Tiếng Anh" };
export const labels: Record<string, string> = {
  ...interests,
  ...values,
  ...styles,
  ...goals,
  ...languages,
};
export const moodLabels = [
  "Rất khó chịu",
  "Hơi khó chịu",
  "Bình thường",
  "Khá dễ chịu",
  "Rất dễ chịu",
];
export const sampleProfile = (): Profile => ({
  interests: ["reading", "music", "walking"],
  values: ["respect", "sincerity"],
  style: "balanced",
  goal: "shared-interests",
  languages: ["vi"],
  sources: [],
});
const candidate = (
  id: string,
  alias: string,
  color: string,
  i: string[],
  v: string[],
  style: string,
  lang = ["vi"],
): Candidate => ({
  id,
  alias,
  color,
  profile: {
    interests: i,
    values: v,
    style,
    goal: "shared-interests",
    languages: lang,
    sources: [],
  },
  version: 1,
  consentVersion: 1,
  allowed: true,
  identity: {
    displayName: alias.split(" ")[0],
    gender: "Không chia sẻ",
    displayNameVersion: 1,
    genderVersion: 1,
  },
});
export const candidateSeed = (): Candidate[] => [
  candidate(
    "C01",
    "Lá Non",
    "sage",
    ["reading", "music", "cooking"],
    ["respect", "sincerity"],
    "balanced",
  ),
  candidate(
    "C02",
    "Suối Nhỏ",
    "blue",
    ["reading", "walking", "english"],
    ["respect", "curiosity"],
    "listening",
    ["vi", "en"],
  ),
  candidate(
    "C03",
    "Nắng Mai",
    "peach",
    ["music", "walking", "photography"],
    ["respect", "sincerity"],
    "direct",
  ),
  candidate(
    "C04",
    "Mầm Xanh",
    "sage",
    ["reading", "music", "walking"],
    ["respect", "sincerity"],
    "listening",
  ),
  candidate(
    "C05",
    "Đồi Gió",
    "peach",
    ["reading", "music", "walking"],
    ["respect", "sincerity"],
    "balanced",
    ["en"],
  ),
];
export const scenarios = {
  AIC01: {
    name: "Ngày học nhiều việc",
    prompts: ["Hôm nay mình hơi mệt.", "Mình muốn ghi lại cảm giác."],
    replies: [
      "Nghe như hôm nay khá dài với bạn rồi. Bạn muốn kể thêm một chút hay ghi lại cảm xúc hôm nay?",
      "Mình ở đây nhé. Thử dừng một nhịp và chọn cảm xúc gần với bạn nhất lúc này.",
    ],
  },
  AIC02: {
    name: "Sở thích",
    prompts: [
      "Mình muốn thử điều gì đó mới.",
      "Mình muốn dành thời gian đọc sách.",
    ],
    replies: [
      "Nghe thú vị đó! Có điều gì bạn từng muốn học hoặc thử nhưng chưa bắt đầu không?",
      "Có vẻ đọc sách là khoảng nghỉ bạn yêu thích. Bạn muốn giữ điều này trong hồ sơ riêng không?",
    ],
  },
  AIC03: {
    name: "Tìm bạn cùng học",
    prompts: [
      "Mình muốn có bạn cùng luyện tiếng Anh.",
      "Mình muốn thử nói về sách.",
    ],
    replies: [
      "Có người cùng học sẽ vui hơn nhỉ! Bạn có thể tìm người cũng thích tiếng Anh trong Tìm bạn.",
      "Sách là một khởi đầu hay đó. Bạn tự chọn sở thích muốn chia sẻ trong hồ sơ kết nối nhé.",
    ],
  },
};
export const fallback =
  "Bản trải nghiệm chỉ có phản hồi soạn sẵn. Bạn có thể chọn một chủ đề mẫu hoặc chuyển sang ghi tâm trạng.";
export const humanPrompts = [
  "Dạo này bạn đang đọc gì?",
  "Bạn muốn học cùng như thế nào?",
  "Thử một câu hỏi làm quen nhé?",
];
export const humanReplies = [
  "Mình đang đọc một tập truyện ngắn. Còn bạn, có cuốn nào muốn giới thiệu không?",
  "Mình thích bắt đầu bằng 15 phút cùng học, rồi kể nhau nghe một điều mới.",
  "Hay là thử vài câu hỏi làm quen trước nhé? Biết đâu lại có thêm một điểm chung!",
];
export const questions = [
  {
    text: "Nếu có một ngày không lo deadline, bạn sẽ làm gì?",
    options: ["Đọc sách", "Đi bộ", "Nghe nhạc"],
    reply: "Trong ví dụ này, mình chọn đọc sách.",
  },
  {
    text: "Bạn muốn thử điều gì mà ít người biết?",
    options: ["15 phút", "Một chủ đề nhỏ", "Mình chưa rõ"],
    reply: "Mình muốn bắt đầu từ một chủ đề nhỏ.",
  },
  {
    text: "Nếu cùng học một kỹ năng mới, bạn chọn gì?",
    options: ["Một câu hỏi", "Một sở thích", "Một kế hoạch"],
    reply: "Mình muốn kể về một sở thích.",
  },
];
export function initialState(epoch = 1): State {
  return {
    epoch,
    bots: initialThreads(),
    age: "unknown",
    ready: false,
    fixtureId: "fresh",
    clock: Date.parse("2026-10-22T19:00:00+07:00"),
    seq: 0,
    consent: { AI: false, MEM: false, MATCH: false, VOICE: false },
    versions: { AI: 0, MEM: 0, MATCH: 0, VOICE: 0 },
    draft: {
      interests: [],
      values: [],
      style: "",
      goal: "",
      languages: [],
      sources: [],
    },
    profileVersion: 0,
    privateItems: [],
    moods: [],
    candidates: candidateSeed(),
    ai: {
      messages: [],
      scenario: "",
      turn: 0,
      error: false,
      voice: "idle",
      transcript: "",
    },
    requests: [],
    connections: [],
    reveals: [],
    activities: [],
    blocked: [],
    cooldowns: {},
    identities: {
      displayName: "An",
      gender: "Không chia sẻ",
      displayNameVersion: 1,
      genderVersion: 1,
    },
    reports: [],
    jobs: [],
    errorOnce: false,
    outcome: "reply",
    notice: "",
  };
}
export function seedSession(s: State) {
  s.privateItems = [
    {
      id: "PI01",
      text: "Mình thích đọc sách",
      origin: "declared",
      status: "confirmed",
      version: 1,
      memoryApproved: false,
    },
    {
      id: "PI02",
      text: "Mình coi trọng sự tôn trọng",
      origin: "declared",
      status: "confirmed",
      version: 1,
      memoryApproved: false,
    },
    {
      id: "AI01",
      text: "Có vẻ bạn thích có câu hỏi gợi mở ngắn",
      origin: "ai",
      status: "proposed",
      version: 1,
      memoryApproved: false,
    },
  ];
  s.moods = [16, 17, 18, 20, 21].map((d, i) => ({
    id: `MD0${i + 1}`,
    date: `2026-10-${d}`,
    value: [3, 2, 4, 3, 4][i],
    note: [
      "Một ngày theo lịch quen thuộc",
      "Nhiều việc cần hoàn thành",
      "Có thời gian đọc sách",
      "",
      "Đi bộ một lúc",
    ][i],
    version: 1,
    time: s.clock - (22 - d) * 86400000,
  }));
}

// Personality-specific scripts; all replies remain explicitly simulated in UI.
export const peerReplies: Record<string, string[]> = {
  C01: humanReplies,
  C02: [
    "Mình đang luyện tiếng Anh mỗi tối. Hay thử kể về một cuốn sách bằng vài câu đơn giản nhé?",
    "Mình thích đi dạo sau giờ học. Vừa đi vừa nghĩ ra nhiều ý tưởng mới.",
    "Mình cũng hơi ngại lúc đầu. Thử một câu hỏi làm quen nhé?",
  ],
  C03: [
    "Mình vừa có một playlist mới để nghe khi đi chụp ảnh. Bạn thích nhạc gì?",
    "Chiều có nắng đẹp là mình muốn ra ngoài đi bộ ngay!",
    "Thử một trò nhỏ nhé? Mình tò mò xem hai đứa có chọn giống nhau không.",
  ],
  C04: [
    "Mình thích mang theo sách khi đi dạo. Một góc yên tĩnh là đủ vui rồi.",
    "Mình thích nghe người khác kể về những điều nhỏ trong ngày. Hôm nay bạn có gì vui?",
    "Không cần vội đâu, cùng thử một câu hỏi trước nhé.",
  ],
};

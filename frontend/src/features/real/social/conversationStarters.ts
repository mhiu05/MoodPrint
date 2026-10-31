import type { components } from "../../../api/generated/schema";
import type { Taxonomy } from "./profileRules";

const TEMPLATES = {
  music: [
    "Có bài hát nào bạn có thể nghe đi nghe lại cả ngày không?",
    "Dạo này bạn hay nghe bài hát nào?",
  ],
  coffee: [
    "Bạn thích cà phê ở quán quen hay tự pha hơn?",
    "Nếu chọn một món cà phê hôm nay, bạn sẽ chọn gì?",
  ],
  movies: [
    "Có bộ phim nào gần đây khiến bạn muốn kể cho một người bạn không?",
    "Bạn thường chọn phim theo thể loại hay theo tâm trạng?",
  ],
  reading: [
    "Có cuốn sách nào bạn muốn giới thiệu cho một người bạn không?",
    "Bạn thích đọc một mạch hay mỗi ngày một chút?",
  ],
  games: [
    "Bạn thích chơi game một mình hay cùng bạn bè hơn?",
    "Có trò chơi nào bạn muốn rủ một người bạn cùng thử không?",
  ],
  travel: [
    "Bạn thích một chuyến đi được lên kế hoạch hay tùy hứng hơn?",
    "Nếu có một ngày rảnh để đi chơi, bạn muốn ghé đâu?",
  ],
  generic: [
    "Gần đây có điều gì nho nhỏ làm bạn thấy vui không?",
    "Bạn muốn bắt đầu làm quen bằng câu chuyện gì?",
  ],
} as const;
const PRIORITY = [
  "music",
  "coffee",
  "movies",
  "reading",
  "games",
  "travel",
] as const;
/** Server wording plus actual peer ID is necessary evidence. No viewer draft input. */
export function selectConversationStarter(
  card: components["schemas"]["CandidateCardDTO"],
  taxonomy: Pick<Taxonomy, "interests">,
) {
  const topic =
    PRIORITY.find(
      (id) =>
        taxonomy.interests[id] &&
        card.profile.interests?.includes(id) &&
        card.reasons.includes(
          `Cùng thích ${taxonomy.interests[id].toLowerCase()}`,
        ),
    ) ?? "generic";
  let hash = 0;
  for (const character of `${card.avatarSeed}|${card.profileVersion}|${card.peerVersion}|starter-v1`)
    hash = (Math.imul(hash, 31) + character.charCodeAt(0)) >>> 0;
  const variant = hash % 2;
  return {
    templateId: `starter-v1:${topic}:${variant}`,
    text: TEMPLATES[topic][variant],
  };
}

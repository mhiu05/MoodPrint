import type { BotId, BotMessage } from "./registry";

// Deliberately scripted. Inputs stay in their own thread; no cross-bot context.
export function scriptedReply(
  id: BotId,
  text: string,
  turn: number,
): Pick<BotMessage, "text" | "card"> {
  const input = text.toLocaleLowerCase("vi-VN");
  switch (id) {
    case "may":
      if (/cảm xúc|ghi lại/.test(input))
        return {
          text: "Bạn có thể ghi lại với Nhịp. Chỉ mở cuộc trò chuyện mới, không chuyển những điều bạn kể ở đây.",
          card: { kind: "handoff", botId: "nhip" },
        };
      if (/đổi chủ đề/.test(input))
        return {
          text: "Được chứ. Hôm nay có bài hát nào bạn muốn nghe lại không?",
        };
      return {
        text:
          turn % 2 === 0
            ? "Một ngày dài à? Bạn muốn kể mình nghe chuyện gì đã xảy ra không?"
            : "Mình đang nghe đây. Bạn muốn được lắng nghe thêm, hay dành một chút thời gian nghỉ cho mình?",
        ...(turn % 2 === 1
          ? { card: { kind: "handoff" as const, botId: "nhip" as const } }
          : {}),
      };
    case "guong":
      if (/nghĩ thêm/.test(input))
        return { text: "Cứ thong thả nhé. Khi nào muốn kể thêm, mình ở đây." };
      if (/coi trọng/.test(input))
        return {
          text: "Khi ở cạnh một người bạn, điều gì khiến bạn cảm thấy thoải mái nhất?",
        };
      if (turn % 2 === 0)
        return {
          text: /đọc|sách/.test(input)
            ? "Khi đọc sách, bạn thích nhất cảm giác yên tĩnh hay được bước vào một thế giới mới?"
            : "Điều gì ở trải nghiệm đó khiến bạn muốn quay lại?",
        };
      return {
        text: "Bạn có thấy điều này đúng với mình không? Bạn có thể sửa trước khi lưu.",
        card: {
          kind: "profile",
          text: /đọc|sách/.test(input)
            ? "Mình thích dành thời gian đọc sách"
            : `Mình trân trọng: ${text.trim().slice(0, 90)}`,
        },
      };
    case "nhip":
      if (/tuần|xu hướng/.test(input))
        return {
          text: "Cùng nhìn lại những ngày bạn đã tự ghi nhé.",
          card: { kind: "insight" },
        };
      if (/thói quen/.test(input))
        return {
          text: "Thử dành hai phút cuối ngày cho một bài hát yêu thích nhé. Bỏ lỡ một hôm cũng không sao.",
        };
      return {
        text: "Không cần phải thấy vui mỗi ngày. Lúc này, bạn thấy gần với cảm giác nào?",
        card: { kind: "mood" },
      };
    case "rure":
      if (/người|bạn cùng/.test(input))
        return {
          text: "Có bạn cùng thử sẽ vui hơn. Bạn tự chọn điều muốn chia sẻ trước nhé.",
          card: { kind: "match" },
        };
      return {
        text: /học/.test(input)
          ? "Một từ mới cho hôm nay: serendipity — tình cờ tìm thấy một điều hay. Thử đặt một câu nhé?"
          : "Khởi động nhẹ nhé. Cái gì càng lấy đi lại càng lớn?",
        card: {
          kind: "activity",
          mode: /học/.test(input) ? "learn" : "puzzle",
        },
      };
    case "caunoi":
      return {
        text: /hồ sơ/.test(input)
          ? "Chọn sở thích và điều bạn muốn tìm ở một người bạn. Bạn sẽ xem trước trước khi chia sẻ."
          : /anh/.test(input)
            ? "Cùng học là một khởi đầu hay! Chọn tiếng Anh trong hồ sơ kết nối để tìm đúng điểm chung nhé."
            : "Một cuốn sách, một bài hát hay một buổi đi bộ đều có thể mở đầu câu chuyện.",
        card: { kind: "match" },
      };
  }
}

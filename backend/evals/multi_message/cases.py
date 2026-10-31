"""Synthetic Vietnamese prompts with the splitting behaviour each one expects.

kind:
- ``short``: a brief exchange; the reply must be exactly one bubble.
- ``list``: asks for steps/a list; the list must never be split across bubbles.
- ``open``: splitting is allowed (acknowledge, then a separate question or idea).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Case:
    case_id: str
    bot_id: str
    kind: str
    prompt: str


CASES: tuple[Case, ...] = (
    Case("MM-SHORT-01", "may", "short", "Cảm ơn Mây nhé."),
    Case("MM-SHORT-02", "may", "short", "Ok mình hiểu rồi."),
    Case("MM-SHORT-03", "guong", "short", "Ừ đúng vậy."),
    Case("MM-SHORT-04", "nhip", "short", "Hôm nay mình ổn."),
    Case("MM-SHORT-05", "rure", "short", "Mình làm xong thử thách rồi!"),
    Case("MM-SHORT-06", "caunoi", "short", "Câu mở lời đó được đấy."),
    Case("MM-SHORT-07", "may", "short", "Chúc ngủ ngon."),
    Case("MM-SHORT-08", "rure", "short", "Haha vui ghê."),
    Case("MM-LIST-01", "nhip", "list", "Gợi ý cho mình 3 bước để ngủ sớm hơn."),
    Case("MM-LIST-02", "rure", "list", "Liệt kê 4 trò chơi một mình trong nhà."),
    Case("MM-LIST-03", "caunoi", "list", "Cho mình 3 câu mở lời khác nhau."),
    Case("MM-LIST-04", "guong", "list", "Mình nên tự hỏi những câu gì để hiểu giá trị của mình? Cho 3 câu."),
    Case("MM-LIST-05", "nhip", "list", "Các bước ghi nhật ký buổi tối là gì?"),
    Case("MM-LIST-06", "may", "list", "Kể 3 cách thả lỏng khi căng thẳng."),
    Case("MM-OPEN-01", "may", "open", "Hôm nay mình thấy hơi buồn mà không rõ vì sao."),
    Case("MM-OPEN-02", "guong", "open", "Mình hay bỏ dở việc giữa chừng."),
    Case("MM-OPEN-03", "nhip", "open", "Mấy hôm nay mình ngủ muộn quá."),
    Case("MM-OPEN-04", "rure", "open", "Chán quá, có gì làm không?"),
    Case("MM-OPEN-05", "caunoi", "open", "Mình ngại nhắn tin trước với người mới quen."),
    Case("MM-OPEN-06", "may", "open", "Mình vừa cãi nhau với bạn thân."),
)

import type { ChatMessage } from "../../types";

export interface Scenario {
  id: string;
  title: string;
  category: string;
  age: number;
}
const catalog: [string, string, number][] = [
  ["Bị gọi bằng biệt danh không thích", "Lời nói", 12],
  ["Một lần tranh cãi với bạn", "Mâu thuẫn", 13],
  ["Không được tham gia nhóm làm bài", "Cô lập", 14],
  ["Bị xô đẩy ở hành lang", "An toàn", 15],
  ["Bị chế giễu trong nhóm lớp", "Trực tuyến", 15],
  ["Tài khoản mạo danh", "Trực tuyến", 16],
  ["Tin nhắn hẹn gặp làm mình sợ", "An toàn", 14],
  ["8 ảnh chụp và lời kể ở lớp", "Nhiều nguồn", 15],
  ["Ảnh riêng tư bị lan truyền", "Trực tuyến", 17],
  ["Bị ép tham gia trò đùa hại bạn", "Người chứng kiến", 13],
  ["Thấy một bạn bị cô lập", "Người chứng kiến", 14],
  ["Muốn nói với giáo viên", "Giao tiếp", 16],
  ["Sợ bố mẹ phản ứng mạnh", "Giao tiếp", 12],
  ["Không nhớ rõ khi giáo viên hỏi", "Giao tiếp", 15],
  ["Đã nhờ giúp nhưng chưa có phản hồi", "Giao tiếp", 16],
  ["Lời đồn trên hai nền tảng", "Nhiều nguồn", 17],
  ["Bắt nạt có nghĩa là gì?", "Kiến thức", 11],
  ["Chưa rõ bạn có cố ý bỏ mình ra ngoài", "Chưa rõ", 13],
  ["Một bình luận ác ý của người lạ", "Trực tuyến", 14],
  ["Lời xúc phạm kéo dài nhiều tháng", "Lặp lại", 15],
  ["Không nhớ chính xác ngày", "Thiếu dữ liệu", 12],
  ["Giờ trong ảnh khác lời mình nhớ", "Mâu thuẫn dữ liệu", 17],
  ["Hai ảnh chụp có thể trùng", "Bằng chứng", 14],
  ["Đang sợ đi một mình", "An toàn", 15],
  ["Chuyện ở trường ảnh hưởng giấc ngủ", "Sức khỏe tinh thần", 16],
  ["Muốn soạn báo cáo bằng bí danh", "Hỗ trợ", 14],
  ["Muốn biết trường đã nhận chưa", "Hỗ trợ", 13],
  ["Muốn sửa cách nói khi nóng giận", "Tự nhìn lại", 17],
  ["Chưa biết báo nội dung trên mạng", "Kiến thức", 15],
  ["Nhìn lại bước đã làm sau hai tuần", "Theo dõi", 16],
];
export const scenarios: Scenario[] = catalog.map(
  ([title, category, age], index) => ({
    id: `SC-${String(index + 1).padStart(2, "0")}`,
    title,
    category,
    age,
  }),
);

export interface ChatFixture {
  id: string;
  scenarioId: string;
  title: string;
  messages: ChatMessage[];
  unknowns: string[];
  observation: string;
  indication: string;
  nextStep: string;
  articleTopic: string;
  urgent?: boolean;
}
function chat(
  index: number,
  scenarioId: string,
  turns: string[],
  observation: string,
  indication: string,
  unknowns: string[],
  nextStep: string,
  articleTopic: string,
  urgent = false,
): ChatFixture {
  const id = `CHAT-${String(index).padStart(2, "0")}`;
  return {
    id,
    scenarioId,
    title: scenarios.find((item) => item.id === scenarioId)!.title,
    messages: turns.map((body, i) => ({
      id: `${id}-${i}`,
      speaker: i % 2 ? "ai" : "user",
      body,
      ...(i === turns.length - 1
        ? { rich: true, sourceIds: [scenarioId] }
        : {}),
    })),
    observation,
    indication,
    unknowns,
    nextStep,
    articleTopic,
    urgent,
  };
}
export const chatFixtures: ChatFixture[] = [
  chat(
    1,
    "SC-01",
    [
      "Các bạn gọi mình bằng tên mình ghét.",
      "Bạn có thể kể từng chút một. Chuyện này xảy ra nhiều lần không?",
      "Khoảng hai tuần rồi, dù mình đã nói là không thích.",
      "Bạn đã nói rõ ranh giới. Điều đó ảnh hưởng tới bạn thế nào?",
      "Mình ngại đến lớp và muốn nói với cô.",
      "Mình có thể giúp ghi lại lời kể và chuẩn bị lời nhắn. Chưa đủ thông tin để kết luận động cơ của các bạn.",
    ],
    "Bạn kể việc gọi biệt danh lặp lại khoảng hai tuần.",
    "Việc tiếp diễn sau khi bạn nói không thích là điều nên trao đổi với người lớn.",
    [
      "Ngày, nơi và những lần cụ thể chưa rõ.",
      "Chưa biết phản hồi của giáo viên.",
    ],
    "Ghi một ví dụ gần đây, rồi chọn người bạn tin để nói chuyện.",
    "Lời nói",
  ),
  chat(
    2,
    "SC-02",
    [
      "Mình vừa cãi nhau với bạn.",
      "Chuyện đã xảy ra mấy lần? Có ai đang không an toàn không?",
      "Chỉ lần này thôi. Bây giờ mình an toàn.",
      "Bạn muốn điều gì khi nói lại với bạn ấy?",
      "Mình muốn xin lỗi vì lớn tiếng và nói rõ cách chia việc.",
      "Một lần cãi nhau chưa đủ để gán nhãn bắt nạt. Bạn có thể luyện câu mở đầu bình tĩnh khi cả hai sẵn sàng.",
    ],
    "Bạn kể một lần tranh cãi và hiện tại an toàn.",
    "Có thể cần trao đổi lại cách chia việc; chưa đủ căn cứ về sự lặp lại.",
    [
      "Chưa biết góc nhìn của bạn kia.",
      "Chưa rõ hai bạn đã thống nhất điều gì.",
    ],
    "Luyện câu: Mình xin lỗi vì đã lớn tiếng. Mình muốn cùng chia lại việc.",
    "Mâu thuẫn",
  ),
  chat(
    3,
    "SC-08",
    [
      "Mình muốn xem 8 ảnh chụp nhóm lớp mẫu.",
      "Đây là ảnh hư cấu dựng sẵn. Bạn có thấy an toàn hôm nay không?",
      "Trong tình huống mẫu, mình đang ở nhà và an toàn.",
      "Bạn muốn giữ cả thông tin chưa rõ để kiểm tra lại cùng ảnh gốc chứ?",
      "Có, mình muốn xem từng nguồn trước khi lưu.",
      "Mở bộ ảnh mẫu để rà soát. Chỉ nội dung bạn xác nhận mới thành mốc; ảnh gần trùng không làm tăng số sự việc.",
    ],
    "Bộ mẫu có tám ảnh, hiển thị các ngày 12–16/10.",
    "Có lời gọi biệt danh và một tin hẹn gặp cần hỏi thêm ngữ cảnh.",
    [
      "Tên bị che và phần bị cắt không thể khôi phục.",
      "Chưa xác định câu hẹn có phải lời đe dọa.",
    ],
    "Mở phân tích ảnh mẫu và kiểm tra từng nguồn.",
    "Trực tuyến",
  ),
  chat(
    4,
    "SC-03",
    [
      "Mình không được tham gia nhóm.",
      "Điều này xảy ra lần đầu hay thường xuyên?",
      "Ba buổi mình không được chọn. Mình chưa biết lý do.",
      "Mình sẽ giữ riêng sự việc và điều chưa biết. Bạn muốn nhờ ai hỗ trợ?",
      "Mình muốn hỏi giáo viên cách phân nhóm.",
      "Bạn có thể ghi các mốc mình nhớ, đồng thời ghi chưa rõ lý do. Không cần đoán động cơ để xin hỗ trợ.",
    ],
    "Bạn kể ba buổi chưa được tham gia nhóm.",
    "Sự lặp lại cần xem xét thêm; chưa biết có chủ ý hay không.",
    ["Chưa biết tiêu chí phân nhóm.", "Ngày và lớp học cần bổ sung."],
    "Chuẩn bị hỏi giáo viên về cách phân nhóm và điều bạn cần.",
    "Cô lập",
  ),
  chat(
    5,
    "SC-07",
    [
      "Có bạn hẹn mình sau giờ học, mình sợ.",
      "Bạn có đang ở nơi an toàn, có người lớn ở gần không?",
      "Mình đang ở trong lớp, cô còn ở đây.",
      "Bạn có thể ở gần cô và nói mình đang lo không? Bạn không cần tự đi gặp nhóm đó.",
      "Mình sẽ nhờ cô ở cùng và xem tin nhắn.",
      "Ưu tiên hỗ trợ trực tiếp. Bạn có thể mở Hỗ trợ ngay và tự chọn người lớn phù hợp. Bản demo không liên hệ ai thay bạn.",
    ],
    "Bạn kể tin hẹn gặp làm mình sợ; hiện có giáo viên ở gần.",
    "Cần ưu tiên hỗ trợ trực tiếp, chưa kết luận ý định người gửi.",
    [
      "Chưa rõ ngữ cảnh đầy đủ của tin nhắn.",
      "Ứng dụng không biết tình trạng thực tế.",
    ],
    "Ở gần người lớn đáng tin cậy và nói rõ bạn đang lo.",
    "An toàn",
    true,
  ),
  chat(
    6,
    "SC-11",
    [
      "Mình thấy một bạn bị cô lập.",
      "Bạn trực tiếp thấy điều gì, và có thể tìm người lớn nào?",
      "Mình thấy nhóm bảo không cho bạn tham gia.",
      "Bạn có thể kể điều đó với giáo viên mà không tự đối đầu không?",
      "Mình muốn kể với cô, chỉ điều mình thấy.",
      "Bạn có thể kể sự việc và điều chưa rõ. Không cần tự đối đầu hoặc tìm thêm thông tin khiến bạn không an toàn.",
    ],
    "Bạn trực tiếp nghe lời từ chối tham gia nhóm.",
    "Đây là điều người lớn có thể cùng tìm hiểu.",
    [
      "Chưa biết sự việc có lặp lại.",
      "Chưa biết bạn ấy muốn được hỗ trợ thế nào.",
    ],
    "Luyện lời kể của người chứng kiến với người lớn đáng tin.",
    "Người chứng kiến",
  ),
  chat(
    7,
    "SC-13",
    [
      "Mình sợ kể với mẹ.",
      "Điều gì làm bạn lo? Có người lớn nào khác bạn tin tưởng không?",
      "Mình sợ mẹ giận. Mình có thể nói với dì.",
      "Bạn muốn người nghe làm gì trước: lắng nghe hay cùng nghĩ cách?",
      "Mình muốn được nghe hết trước khi người lớn quyết định.",
      "Bạn có thể bắt đầu bằng mong muốn đó và kể một việc nhỏ. Có thể luyện với vai phụ huynh hoặc chọn người lớn khác.",
    ],
    "Bạn lo phản ứng của mẹ và có người lớn khác tin tưởng.",
    "Luyện câu mở đầu có thể giúp bạn nói rõ mong muốn.",
    [
      "Chưa biết người lớn sẽ phản hồi thế nào.",
      "Bạn quyết định phần nào sẵn sàng chia sẻ.",
    ],
    "Thử luyện câu: Con muốn được lắng nghe hết trước khi mình quyết định.",
    "Giao tiếp",
  ),
  chat(
    8,
    "SC-19",
    [
      "Người lạ nói xấu mình một lần.",
      "Có liên quan trường lớp và có lặp lại không?",
      "Không liên quan trường lớp, mới thấy một lần.",
      "Bạn muốn xem cách báo nội dung hay ghi lại điều đã thấy?",
      "Mình muốn xem hướng dẫn báo nội dung.",
      "Một bình luận vẫn có thể làm bạn khó chịu. Chưa đủ dấu hiệu gọi đây là bắt nạt học đường. Có thể xem hướng dẫn chính thức của nền tảng.",
    ],
    "Bạn kể một bình luận ác ý từ người lạ.",
    "Có thể cần dùng công cụ chặn hoặc báo nội dung phù hợp.",
    [
      "Chưa biết nền tảng và nội dung đầy đủ.",
      "Không xác định được danh tính người gửi.",
    ],
    "Xem nguồn chính thức trước khi tự chọn chặn hoặc báo nội dung.",
    "Trực tuyến",
  ),
  chat(
    9,
    "SC-21",
    [
      "Mình không nhớ ngày xảy ra.",
      "Bạn nhớ khoảng thời gian, tiết học hoặc nơi nào không?",
      "Khoảng giữa tuần trước, ở sân trường.",
      "Bạn muốn ghi khoảng đó và giữ nhãn chưa rõ ngày không?",
      "Có, mình không muốn đoán ra một ngày.",
      "Bạn có thể ghi không rõ ngày cùng phần mình nhớ. Nói rõ điều chưa chắc giúp bản ghi trung thực hơn; không cần bịa mốc thời gian.",
    ],
    "Bạn nhớ khoảng giữa tuần trước, tại sân trường.",
    "Có thể lưu mốc với độ chính xác thời gian chưa rõ.",
    ["Không rõ ngày và giờ cụ thể."],
    "Lưu lời kể với nhãn không rõ ngày; bổ sung sau nếu nhớ thêm.",
    "Ghi nhận",
  ),
  chat(
    10,
    "SC-22",
    [
      "Ảnh ghi khác thời gian mình nhớ.",
      "Bạn muốn giữ cả hai thông tin để kiểm tra lại chứ?",
      "Mình nhớ 18 giờ nhưng ảnh mẫu ghi 20:10.",
      "Đó là giờ hiển thị trong ảnh, hay thời điểm chụp?",
      "Mình chỉ thấy giờ trong đoạn chat, chưa biết lúc chụp.",
      "Mình sẽ giữ lời kể 18 giờ riêng với giờ hiển thị 20:10. Cần xem lại sự khác nhau, không tự chọn bên nào sai.",
    ],
    "Lời kể ghi 18:00; MEDIA-03 hiển thị 20:10.",
    "Có mâu thuẫn thời gian cần giữ cả hai nguồn.",
    ["Không biết thời điểm chụp.", "Chưa biết vì sao hai mốc khác nhau."],
    "Mở mẫu mâu thuẫn thời gian để so từng nguồn.",
    "Bằng chứng",
  ),
  chat(
    11,
    "SC-25",
    [
      "Mình khó ngủ vì chuyện ở trường.",
      "Bạn muốn kể thêm hay tìm người hỗ trợ để nói chuyện?",
      "Mình muốn kể với người lớn nhưng chưa biết bắt đầu.",
      "Có ai bạn tin và muốn nhờ họ lắng nghe không?",
      "Mình muốn nói với cô chuyện này ảnh hưởng việc học.",
      "Bạn có thể mô tả ảnh hưởng bằng lời mình và nhờ hỗ trợ. Bản demo không chẩn đoán sức khỏe hoặc thay cuộc trao đổi trực tiếp.",
    ],
    "Bạn kể khó ngủ và bị ảnh hưởng việc học.",
    "Đây là điều có thể chia sẻ để được người lớn hỗ trợ.",
    [
      "Chưa biết mức độ và thời gian kéo dài.",
      "Không thể đưa ra chẩn đoán từ hội thoại này.",
    ],
    "Chuẩn bị lời nhắn nêu ảnh hưởng và đề nghị được trò chuyện.",
    "Sức khỏe tinh thần",
  ),
  chat(
    12,
    "SC-30",
    [
      "Tuần trước mình đã nhờ cô giúp.",
      "Cô đã phản hồi điều gì? Có điều gì đã thay đổi?",
      "Cô hẹn nói chuyện lại, nhưng chưa có lịch.",
      "Bạn muốn chuẩn bị lời hỏi lại và ngày xem lại kế hoạch không?",
      "Có, mình muốn hỏi khi nào có thể trao đổi tiếp.",
      "Bạn có thể ghi điều đã làm rồi chuẩn bị hỏi lại. Hoàn tất một bước không có nghĩa chuyện đã được giải quyết hoặc trường đã nhận báo cáo.",
    ],
    "Bạn đã nói với cô và chưa có lịch trao đổi tiếp.",
    "Có thể chuẩn bị một bước theo dõi cụ thể.",
    ["Chưa có phản hồi hoặc lịch hẹn được xác nhận."],
    "Mở kế hoạch của hồ sơ liên quan và đặt bước hỏi lại.",
    "Theo dõi",
  ),
];

export type Role = "teacher" | "parent" | "support";
export interface RoleplayScript {
  id: string;
  role: Role;
  title: string;
  scenarioId: string;
  goal: string;
  prompts: string[];
  replies: string[];
  strength: string;
  improve: string;
  example: string;
}
export const roleLabels: Record<Role, string> = {
  teacher: "Giáo viên",
  parent: "Phụ huynh",
  support: "Người lớn tin cậy",
};
export function getRoleplayPrompt(
  script: RoleplayScript,
  index: number,
  tone: string,
): string {
  const prompt = script.prompts[index] ?? script.prompts.at(-1)!;
  if (tone === "neutral" || index >= script.replies.length) return prompt;
  const gentle: Record<Role, string> = {
    teacher: "Em có thể nói chậm, cô đang lắng nghe. ",
    parent: "Con có thể kể từng chút một. ",
    support: "Em cứ kể phần mình thấy thoải mái. ",
  };
  const detailed: Record<Role, string> = {
    teacher: "Cô sẽ hỏi một chi tiết để mình kiểm tra rõ: ",
    parent: "Mình cùng làm rõ một chi tiết nhé: ",
    support: "Để tránh suy đoán, mình cùng làm rõ: ",
  };
  return (tone === "gentle" ? gentle : detailed)[script.role] + prompt;
}
export const roleplayScripts: RoleplayScript[] = [
  {
    id: "RP-TEACHER-01",
    role: "teacher",
    title: "Lần đầu kể với giáo viên",
    scenarioId: "SC-12",
    goal: "Kể một sự việc và đề nghị giúp đỡ",
    prompts: [
      "Em muốn cô biết chuyện gì đang xảy ra?",
      "Em nhớ một ví dụ gần đây nhất không?",
      "Em mong cô hỗ trợ cụ thể điều gì trước?",
      "Mình đã có sự việc, ví dụ và mong muốn để chuẩn bị cuộc trao đổi thật.",
    ],
    replies: [
      "Các bạn hay chế giễu em trong nhóm lớp.",
      "Hôm thứ Hai có tin nhắn như vậy, em đã chụp lại.",
      "Em muốn cô giúp tìm cách để chuyện dừng lại và hỏi em trước khi chia sẻ thêm.",
    ],
    strength: "Bạn đã luyện nêu sự việc, một ví dụ và yêu cầu hỗ trợ.",
    improve: "Có thể bổ sung khoảng thời gian và hỏi cách liên hệ tiếp.",
    example:
      "Em muốn kể một việc làm em lo. Cô có thể nghe em và cùng chọn bước tiếp theo không?",
  },
  {
    id: "RP-TEACHER-02",
    role: "teacher",
    title: "Khi người nghe hỏi chi tiết",
    scenarioId: "SC-14",
    goal: "Nói rõ điều nhớ và điều chưa chắc",
    prompts: [
      "Em nhớ chính xác ngày nào chuyện xảy ra?",
      "Không nhớ chính xác cũng được. Có thông tin nào giúp kiểm tra phần em nhớ không?",
      "Em muốn cô hỗ trợ phần nào trước trong khi ngày giờ chưa rõ?",
      "Giữ điều chưa chắc là chưa chắc giúp câu chuyện trung thực.",
    ],
    replies: [
      "Em không chắc ngày, chỉ nhớ khoảng giữa tuần.",
      "Em có ảnh mẫu nhưng muốn kiểm tra lại ngày trên ảnh.",
      "Em muốn cô nghe phần em nhớ và giúp ghi phần cần hỏi lại.",
    ],
    strength: "Bạn đã luyện nói giới hạn trí nhớ mà không tự đặt ngày giờ.",
    improve: "Có thể nêu riêng điều trực tiếp thấy và điều được kể lại.",
    example:
      "Em chưa chắc ngày, nhưng nhớ khoảng giữa tuần và muốn giữ nhãn cần kiểm tra.",
  },
  {
    id: "RP-TEACHER-03",
    role: "teacher",
    title: "Hỏi lại sau lần trao đổi trước",
    scenarioId: "SC-15",
    goal: "Chuẩn bị một cuộc trao đổi tiếp",
    prompts: [
      "Em muốn cập nhật điều gì từ lần trao đổi trước?",
      "Có điều gì thay đổi hoặc vẫn làm em lo?",
      "Em muốn sắp xếp bước trao đổi tiếp thế nào?",
      "Đây là tập chuẩn bị, chưa có lịch hay phản hồi từ trường thật.",
    ],
    replies: [
      "Em muốn hỏi mình có thể cập nhật việc đã nói tuần trước không?",
      "Có lời trêu chọc vẫn tiếp diễn và em chưa biết bước tiếp theo.",
      "Em muốn xin giờ hẹn cùng xem lại và biết có thể tìm ai nếu cần.",
    ],
    strength: "Bạn đã luyện nêu điều đã làm và điều chưa thay đổi.",
    improve: "Thử đề nghị một thời điểm cụ thể để xem lại.",
    example:
      "Cô cho em biết khi nào có thể trao đổi tiếp, và em có thể tìm ai khi cần được không?",
  },
  {
    id: "RP-PARENT-01",
    role: "parent",
    title: "Mở lời khi mình còn ngại",
    scenarioId: "SC-13",
    goal: "Xin được lắng nghe trước",
    prompts: [
      "Con có điều gì muốn kể với bố/mẹ không?",
      "Điều gì làm con thấy khó khăn nhất?",
      "Con mong bố/mẹ làm gì trước để giúp con?",
      "Mình đã tập được cách mở lời. Bạn chọn kể ít hay nhiều khi sẵn sàng.",
    ],
    replies: [
      "Con đang gặp chuyện ở lớp, chưa biết bắt đầu từ đâu.",
      "Có lời trêu chọc làm con lo mỗi khi tới lớp.",
      "Con muốn bố/mẹ nghe hết trước khi quyết định, rồi cùng nghĩ cách.",
    ],
    strength: "Bạn đã luyện mở lời và nêu mong muốn được lắng nghe.",
    improve: "Có thể thêm một ví dụ cụ thể khi sẵn sàng.",
    example:
      "Con muốn kể một việc. Bố/mẹ nghe con hết trước, rồi mình cùng chọn cách giúp con nhé?",
  },
  {
    id: "RP-PARENT-02",
    role: "parent",
    title: "Khi người nghe chưa hiểu",
    scenarioId: "SC-13",
    goal: "Nêu ảnh hưởng bằng cách tôn trọng",
    prompts: [
      "Có phải các bạn chỉ đùa thôi không?",
      "Bố/mẹ muốn hiểu rõ hơn. Con có thể nêu một điều xảy ra và ảnh hưởng tới con không?",
      "Con muốn được giúp thế nào, hoặc muốn nói với người lớn nào khác?",
      "Mình dừng phần tập ở đây. Bạn có quyền chọn người lớn khác mình tin.",
    ],
    replies: [
      "Con biết có thể bố/mẹ chưa rõ, nhưng chuyện làm con sợ và đã lặp lại.",
      "Các bạn vẫn gọi biệt danh dù con nói không thích. Con ngại tới lớp.",
      "Con muốn cùng xem lại một ví dụ và lắng nghe điều con cần.",
    ],
    strength:
      "Bạn đã luyện diễn đạt ảnh hưởng và mong muốn mà không tranh cãi.",
    improve: "Có thể nói ranh giới và chọn người lớn khác để tiếp tục.",
    example:
      "Điều đó làm con lo. Con muốn mình cùng xem lại thay vì kết luận ngay.",
  },
  {
    id: "RP-SUPPORT-01",
    role: "support",
    title: "Kể điều mình đã chứng kiến",
    scenarioId: "SC-11",
    goal: "Phân biệt điều thấy và điều chưa rõ",
    prompts: [
      "Em chứng kiến chuyện gì, và điều gì chưa rõ?",
      "Ai ở gần có thể hỗ trợ để em không phải tự đối đầu?",
      "Em muốn người lớn giúp việc gì tiếp theo?",
      "Buổi tập không gửi thông tin đi; bạn tự quyết định cách tìm người hỗ trợ.",
    ],
    replies: [
      "Em thấy một bạn bị từ chối vào nhóm. Em chưa biết chuyện trước đó.",
      "Có giáo viên ở gần, em có thể trao đổi riêng với cô.",
      "Em muốn cô kiểm tra và hỗ trợ bạn ấy, đồng thời hỏi phần nào có thể chia sẻ.",
    ],
    strength:
      "Bạn đã luyện kể điều trực tiếp thấy và giữ riêng điều chưa biết.",
    improve: "Có thể thêm nơi và khoảng thời gian bạn chứng kiến.",
    example:
      "Em trực tiếp thấy việc này ở lớp. Em chưa rõ lý do và muốn nhờ cô kiểm tra giúp.",
  },
];

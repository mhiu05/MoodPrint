import type { KnowledgeArticle } from "../../types";

const both = ["11–13", "14–17"] as const;
type Entry = {
  id: number;
  slug: string;
  title: string;
  summary: string;
  topic: string;
  format: KnowledgeArticle["format"];
  know: string;
  do: string;
  avoid: string;
  example: string;
  sources: string[];
  scenario?: KnowledgeArticle["scenario"];
  quiz?: KnowledgeArticle["quiz"];
};
const scenario = (
  question: string,
  good: string,
  why: string,
  risky: string,
  risk: string,
  wait: string,
): KnowledgeArticle["scenario"] => ({
  question,
  options: [
    { label: good, feedback: why, helpful: true },
    { label: risky, feedback: risk, helpful: false },
    { label: "Mình chưa sẵn sàng hành động", feedback: wait, helpful: true },
  ],
});
const quiz = (
  question: string,
  options: string[],
  answer: number,
  explanation: string,
): KnowledgeArticle["quiz"] => ({ question, options, answer, explanation });
const entries: Entry[] = [
  {
    id: 1,
    slug: "bat-nat-la-gi",
    title: "Bắt nạt là gì?",
    summary:
      "Nhìn vào hành vi, sự lặp lại và chênh lệch quyền lực — không vội gắn nhãn một người.",
    topic: "Nhận biết",
    format: "faq",
    sources: ["STOP-DEFINITION"],
    know: "Một hành vi gây hại có thể liên quan đến bắt nạt khi có chênh lệch quyền lực và xảy ra lặp lại, hoặc có khả năng tiếp diễn. Sức mạnh không chỉ là thể lực: một nhóm đông hoặc thông tin riêng tư cũng có thể tạo ra chênh lệch.",
    do: "Thử viết riêng ba dòng: chuyện gì đã diễn ra, đã xảy ra bao nhiêu lần, điều gì khiến bạn khó dừng lại hoặc rời đi. Nếu chưa biết, ghi “chưa rõ”.",
    avoid:
      "Không cần tự chứng minh đủ mọi dấu hiệu mới được nhờ giúp. Một việc gây hại dù chỉ xảy ra một lần vẫn đáng được người lớn lắng nghe.",
    example:
      "Ghi nhận mẫu: “Mình bị giấu cặp hai lần trong tuần. Khi xin lại, mình bị cả nhóm vây quanh.” Đây là mô tả hành vi, chưa phải kết luận về từng người.",
  },
  {
    id: 2,
    slug: "treu-dua-hay-bat-nat",
    title: "Trêu đùa, mâu thuẫn hay bắt nạt?",
    summary:
      "Cảm giác khó chịu cần được lắng nghe, ngay cả khi bạn chưa gọi tên được tình huống.",
    topic: "Nhận biết",
    format: "scenario",
    sources: ["STOP-DEFINITION"],
    know: "Xem cả việc có thể nói dừng hay không, hành vi có tiếp diễn không và hai bên có ở vị thế tương đương không. Một ảnh chụp hoặc một câu kể có thể chưa đủ bối cảnh.",
    do: "Bạn có thể mô tả “Mình không thấy vui khi chuyện đó lặp lại” thay vì tranh luận ngay về tên gọi. Nhờ một người lớn cùng xem lại các lần xảy ra.",
    avoid:
      "Đừng ép mình phải cười để chứng tỏ đó chỉ là đùa. Cũng không cần buộc người khác nhận lỗi ngay trong một cuộc đối chất.",
    example:
      "Tình huống do MoodPrint biên tập: một nhóm vẫn nhắc lại biệt danh sau khi bạn đã nói mình khó chịu.",
    scenario: scenario(
      "Bạn sẽ bắt đầu từ đâu?",
      "Ghi lại việc lặp lại và tìm người lớn cùng xem",
      "Cách này làm rõ diễn biến và giúp bạn có thêm hỗ trợ trước khi chọn bước tiếp theo.",
      "Đăng tên cả nhóm lên mạng",
      "Việc công khai có thể làm xung đột lan rộng và lộ thông tin. Bạn có thể kể riêng với người có thể giúp.",
      "Bạn có thể lưu vài dòng cho mình trước, rồi chọn một người để nói khi thấy đủ an toàn.",
    ),
  },
  {
    id: 3,
    slug: "bi-goi-biet-danh",
    title: "Khi một biệt danh khiến bạn tổn thương",
    summary:
      "Thử một câu nói ngắn và chuẩn bị cách rời tình huống nếu lời nói không được tôn trọng.",
    topic: "Trực tiếp",
    format: "scenario",
    sources: ["STOP-DEFINITION"],
    know: "Gọi tên xúc phạm là một dạng hành vi bằng lời. Khi lặp lại và có chênh lệch quyền lực, đó có thể là dấu hiệu cần được xem xét kỹ hơn.",
    do: "Nếu thấy an toàn, thử “Mình muốn được gọi bằng tên của mình”. Chọn chỗ gần người hỗ trợ; ghi lại phản ứng sau khi bạn nêu mong muốn.",
    avoid:
      "Không bắt buộc phải đáp trả thật sắc sảo hay tự nói với cả nhóm. Giữ an toàn quan trọng hơn việc thắng lời qua tiếng lại.",
    example:
      "Mẫu câu do MoodPrint soạn: “Mình đã nói là không thích tên đó. Mình muốn cô giúp để việc này dừng lại.”",
    scenario: scenario(
      "Bạn ở một mình và nhóm đang chặn lối. Bạn chọn gì?",
      "Đi về phía người lớn hoặc nơi có người hỗ trợ",
      "Bạn được ưu tiên rời tình huống. Không cần đứng lại để giải thích với nhóm.",
      "Ở lại và buộc nhóm xin lỗi ngay",
      "Đối chất khi đang bị chặn lối có thể tăng nguy cơ. Hãy nhờ hỗ trợ trực tiếp.",
      "Bạn có thể chưa muốn nói dài; chỉ cần báo “Em cần cô đi cùng” cũng là một bước.",
    ),
  },
  {
    id: 4,
    slug: "khi-bi-co-lap",
    title: "Khi bạn bị gạt khỏi nhóm",
    summary:
      "Tách điều mình biết khỏi điều mình đoán và tìm một kết nối có thể dựa vào.",
    topic: "Cô lập",
    format: "scenario",
    sources: ["STOP-DEFINITION"],
    know: "Cố ý loại ai đó ra khỏi nhóm là một dạng hành vi xã hội cần chú ý. Việc không được mời một lần chưa tự nó cho biết toàn bộ động cơ hay diễn biến.",
    do: "Ghi một việc cụ thể: buổi học nào, hoạt động gì, bạn đã nghe hoặc nhìn thấy điều gì. Thử tìm một người bạn hoặc người lớn có thể đi cùng vào hoạt động tiếp theo.",
    avoid:
      "Đừng tự kết luận mình không xứng đáng có bạn. Cũng tránh ép một người khác phải chọn phe trước mặt mọi người.",
    example:
      "Ghi nhận mẫu: “Trong ba buổi làm bài nhóm, không nhóm nào nhận mình; mình đã hỏi lớp trưởng một lần.”",
    scenario: scenario(
      "Không ai nhận bạn vào nhóm bài tập. Một bước nhỏ là gì?",
      "Nói riêng với giáo viên về cách chia nhóm",
      "Bạn có thể xin một thay đổi cụ thể trong hoạt động mà chưa cần giải thích hết quan hệ trong lớp.",
      "Rời mọi hoạt động và không nói với ai",
      "Nghỉ một chút có thể cần thiết, nhưng cô lập lâu hơn có thể khiến bạn thiếu hỗ trợ. Hãy thử giữ một người biết chuyện.",
      "Bạn có thể viết điều muốn nói trước hoặc nhờ một người bạn đứng cạnh.",
    ),
  },
  {
    id: 5,
    slug: "khi-co-xo-day",
    title: "Nếu có xô đẩy: an toàn trước",
    summary:
      "Bạn không cần thu thập đủ bằng chứng khi đang có nguy cơ bị thương.",
    topic: "Trực tiếp",
    format: "scenario",
    sources: ["STOP-DEFINITION", "VN-111"],
    know: "Đẩy, đánh hoặc làm hỏng đồ là những hành vi có thể gây hại trực tiếp. Nội dung này chỉ giúp chuẩn bị bước tìm người hỗ trợ, không đánh giá thương tích.",
    do: "Nếu có thể rời đi an toàn, tìm nơi có người lớn. Nói ngắn “Em đang bị xô đẩy, em cần giúp ngay”. Nếu bị đau hoặc bị thương, nhờ người lớn tìm trợ giúp y tế phù hợp.",
    avoid:
      "Không ở lại quay phim cho đủ, không hẹn gặp riêng để giải quyết và không giao nhiệm vụ tự giữ người đang gây hại.",
    example:
      "Lời nhờ giúp do MoodPrint soạn: “Cô có thể ở lại cùng em và giúp em ra khỏi chỗ này không?”",
    scenario: scenario(
      "Bạn đang thấy có nguy cơ bị đánh tiếp. Điều nào ưu tiên?",
      "Tìm nơi an toàn và người lớn gần đó",
      "Giúp đỡ trực tiếp phù hợp hơn việc tiếp tục nhập dữ liệu vào ứng dụng khi nguy cơ đang diễn ra.",
      "Đứng lại chụp cho rõ mặt mọi người",
      "Việc thu hình không đáng để bạn ở lại nơi có nguy cơ. Có thể kể điều nhớ được sau khi an toàn.",
      "Bạn không cần nói trọn câu chuyện; có thể chỉ nhờ người lớn ở cạnh ngay bây giờ.",
    ),
  },
  {
    id: 6,
    slug: "bat-nat-online",
    title: "Bắt nạt online có thể trông như thế nào?",
    summary:
      "Tin nhắn, trò chơi và nhóm lớp đều có thể trở thành nơi một người bị làm tổn thương.",
    topic: "Online",
    format: "quiz",
    sources: ["UNICEF-VN"],
    know: "Nội dung gây hại trên không gian số có thể bao gồm tin nhắn đe dọa, lời đồn, ảnh làm xấu hổ hoặc mạo danh. Việc xảy ra trên màn hình không làm cảm giác của bạn kém quan trọng.",
    do: "Chọn một điều có thể thay đổi ngay: tắt thông báo trong lúc nghỉ, xem lại quyền riêng tư, hoặc cùng người lớn xem nội dung bạn đang lo.",
    avoid:
      "Không cần bỏ hoàn toàn mọi kết nối online để chứng minh rằng bạn đã tự bảo vệ mình. Bạn có thể xin giúp cho từng phần khó xử.",
    example:
      "Câu tự nhắc do MoodPrint biên tập: “Mình có quyền tạm rời màn hình và quay lại khi có người hỗ trợ.”",
    quiz: quiz(
      "Điều nào giúp nhận diện vấn đề thay vì xem nhẹ nó?",
      [
        "Chỉ việc ngoài đời mới đáng kể",
        "Xem hành vi, bối cảnh và tác động lên người bị nhắm đến",
        "Ai khó chịu thì phải rời Internet mãi mãi",
      ],
      1,
      "Nhìn vào điều xảy ra và tác động giúp chọn bước hỗ trợ. Không nên coi tổn thương online là ít thật hơn.",
    ),
  },
  {
    id: 7,
    slug: "tin-nhan-de-doa",
    title: "Nhận tin nhắn đe dọa: ghi gì, nhờ ai?",
    summary:
      "Ưu tiên nguy cơ hiện tại, rồi mới lưu thời gian và nội dung nếu làm được an toàn.",
    topic: "Đe dọa",
    format: "scenario",
    sources: ["STOP-REPORT", "VN-111"],
    know: "Tin nhắn đe dọa cần được một người có thể hỗ trợ xem xét. Đừng chờ biết chắc ai đứng sau tài khoản mới kể rằng bạn đang lo sợ.",
    do: "Nếu an toàn, lưu thời điểm nhận, tài khoản hiển thị, nội dung và đường dẫn. Ghi rõ phần nào là bạn thấy trực tiếp; nếu lời đe dọa có vẻ sắp xảy ra, tìm người lớn ngay.",
    avoid:
      "Không trả lời bằng lời đe dọa khác, không đi đến điểm hẹn để kiểm chứng và không mở liên kết lạ để tìm danh tính.",
    example:
      "Tóm tắt mẫu: “Tối nay tài khoản X nói sẽ đợi mình ở cổng. Mình chưa biết ai dùng tài khoản đó.”",
    scenario: scenario(
      "Tin nhắn yêu cầu bạn ra gặp một mình. Bạn làm gì?",
      "Cho người lớn tin cậy xem và không đến gặp riêng",
      "Có người cùng biết giúp bạn lựa chọn an toàn. Bạn không phải kiểm chứng lời đe dọa bằng cách đến đó.",
      "Đến một mình để hỏi cho ra chuyện",
      "Gặp riêng có thể làm tăng nguy cơ. Tìm hỗ trợ trước là lựa chọn phù hợp hơn.",
      "Có thể đưa điện thoại cho người lớn xem nếu bạn chưa muốn kể lại thành lời.",
    ),
  },
  {
    id: 8,
    slug: "luu-anh-chup-co-ngu-canh",
    title: "Lưu ảnh chụp với đủ ngữ cảnh",
    summary: "Một bản ghi dễ hiểu cần cả phần bạn biết và phần còn thiếu.",
    topic: "Online",
    format: "checklist",
    sources: ["STOP-REPORT"],
    know: "Ảnh chụp có thể giúp ghi lại nội dung, nhưng một khung hình bị cắt có thể thiếu phần trước và sau. MoodPrint không xác minh ảnh là thật hay ai đã gửi.",
    do: "Nếu an toàn: giữ bản gốc; ghi ngày chụp khác với ngày hiển thị trong ảnh; thêm nơi nội dung xuất hiện; đánh dấu phần bị cắt hoặc không đọc được. Chỉ chia sẻ với người cần giúp.",
    avoid:
      "Không sửa bản gốc rồi trình bày như chưa chỉnh. Không đăng công khai hình có tên, số điện thoại hoặc nội dung riêng tư của người khác.",
    example:
      "Ghi chú mẫu: “Mình chụp ngày 7/11; trong ảnh chỉ hiện 21:14, không thấy ngày. Thiếu hai tin nhắn phía trên.”",
  },
  {
    id: 9,
    slug: "chan-va-bao-cao-noi-dung",
    title: "Chặn và báo nội dung trên nền tảng",
    summary:
      "Làm từng bước trong công cụ chính thức, với người hỗ trợ nếu cần.",
    topic: "Online",
    format: "checklist",
    sources: ["STOP-REPORT"],
    know: "Nền tảng có cơ chế báo nội dung và chặn tài khoản riêng. Tên nút và trình tự có thể thay đổi; MoodPrint không có kết nối để xử lý báo cáo thay bạn.",
    do: "Mở trung tâm trợ giúp từ chính ứng dụng hoặc website chính thức. Tìm “báo cáo” cho đúng loại nội dung: bài đăng, tài khoản hay tin nhắn. Xem lại nội dung bạn định gửi rồi tự quyết định.",
    avoid:
      "Không đưa mật khẩu cho người hứa “xử lý nhanh”. Không xem việc chặn là bảo đảm rằng nội dung đã biến mất ở mọi nơi.",
    example:
      "Danh sách kiểm tra do MoodPrint soạn: đúng trang chính thức; đúng nội dung; thông tin đính kèm cần thiết; biết nơi xem phản hồi của nền tảng.",
  },
  {
    id: 10,
    slug: "tai-khoan-mao-danh",
    title: "Nếu có tài khoản mang tên hoặc ảnh của bạn",
    summary: "Ghi nhận điều nhìn thấy trước khi phỏng đoán người đứng sau.",
    topic: "Online",
    format: "scenario",
    sources: ["UNICEF-VN"],
    know: "Mạo danh có thể khiến người khác hiểu nhầm ai đã đăng nội dung. Tên và ảnh hiển thị không tự chứng minh danh tính người điều khiển tài khoản.",
    do: "Lưu đường dẫn tài khoản nếu an toàn. Nói với người tin cậy điều bạn không tạo hoặc không gửi, rồi cùng tìm mục báo cáo mạo danh trong trợ giúp chính thức của nền tảng.",
    avoid:
      "Không đăng lời buộc tội một bạn chỉ vì bạn nghi ngờ. Không thử xâm nhập tài khoản để tìm người tạo.",
    example:
      "Mẫu câu: “Mình không dùng tài khoản này. Đây là đường dẫn mình nhìn thấy; mình chưa biết người tạo.”",
    scenario: scenario(
      "Có tài khoản dùng ảnh bạn và nhắn cho lớp. Bước nào có ích?",
      "Lưu đường dẫn và nhờ người lớn cùng kiểm tra",
      "Điều này giữ lại dấu vết và tránh biến nghi ngờ thành lời buộc tội.",
      "Công khai mật khẩu của tài khoản bạn nghi ngờ",
      "Chia sẻ mật khẩu gây nguy hiểm và không chứng minh được ai mạo danh. Hãy dùng kênh báo cáo chính thức.",
      "Bạn có thể bắt đầu bằng một tin nhắn riêng cho người lớn mà chưa cần giải thích với cả lớp.",
    ),
  },
  {
    id: 11,
    slug: "tin-don-trong-nhom-lop",
    title: "Khi tin đồn lan trong nhóm lớp",
    summary: "Giảm việc lan truyền và chọn nơi nói rõ câu chuyện của mình.",
    topic: "Cô lập",
    format: "scenario",
    sources: ["STOP-DEFINITION"],
    know: "Lan truyền lời đồn có thể làm tổn hại quan hệ và danh tiếng. Bạn có thể mô tả nội dung được chia sẻ mà chưa kết luận người khởi đầu.",
    do: "Ghi rõ bạn trực tiếp thấy bài nào, ở đâu; tách với điều được kể lại. Chọn một người lớn có thể giúp dừng việc chia sẻ trong nhóm học tập.",
    avoid:
      "Không chuyển tiếp lời đồn cho thêm nhiều người chỉ để hỏi ai đúng. Không cần viết một bài công khai kể hết chuyện riêng để tự bảo vệ.",
    example:
      "Mẫu ghi nhận: “Mình thấy nội dung trong nhóm bài tập; về nhóm khác, mình mới nghe bạn kể, chưa tự xem.”",
    scenario: scenario(
      "Bạn muốn nhờ giúp về một lời đồn. Cách kể nào rõ nhất?",
      "Nói nội dung đã trực tiếp thấy và phần chỉ nghe kể",
      "Tách nguồn giúp người hỗ trợ hiểu điều nào đã có ngữ cảnh, điều nào còn cần làm rõ.",
      "Khẳng định mọi thành viên đều là người khởi đầu",
      "Một nhóm có nhiều vai trò. Không nên gán trách nhiệm cho từng người khi chưa có thông tin.",
      "Bạn có thể lưu lại một dòng ngắn rồi quyết định chia sẻ thêm khi sẵn sàng.",
    ),
  },
  {
    id: 12,
    slug: "anh-bi-chia-se",
    title: "Ảnh của bạn bị chia sẻ ngoài ý muốn",
    summary:
      "Bạn có thể tìm hỗ trợ mà không cần gửi ảnh đó thêm cho nhiều người.",
    topic: "Ảnh riêng tư",
    format: "scenario",
    sources: ["UNICEF-VN", "VN-111"],
    know: "Bị dùng ảnh để làm xấu hổ có thể gây áp lực lớn. Bạn không phải tự một mình thương lượng với người đang gây áp lực.",
    do: "Nhờ người lớn an toàn cùng xem cách báo nội dung. Mô tả ảnh và vị trí xuất hiện trước; nếu ảnh nhạy cảm liên quan đến trẻ em, đừng tải hoặc chuyển tiếp thêm, tìm hỗ trợ từ người lớn hoặc 111.",
    avoid:
      "Không gửi thêm ảnh, tiền hoặc thông tin để đổi lấy lời hứa xóa ảnh. Không rủ nhóm bạn phát tán lại để “tìm nguồn”.",
    example:
      "Câu mở đầu do MoodPrint soạn: “Có ảnh của em đang bị chia sẻ. Em không muốn chuyển ảnh, nhưng em cần người lớn giúp ngay.”",
    scenario: scenario(
      "Một người hứa xóa ảnh nếu bạn gửi thêm. Bạn chọn gì?",
      "Dừng trao đổi và nhờ người lớn an toàn giúp",
      "Bạn không có lỗi vì bị gây áp lực. Có người hỗ trợ giúp bạn tránh phải tự thương lượng.",
      "Gửi thêm để người đó giữ lời",
      "Gửi thêm có thể làm bạn bị gây áp lực tiếp. Không cần đáp ứng yêu cầu để xứng đáng được giúp.",
      "Nếu khó nói, hãy cho người lớn đọc câu mở đầu trong bài; không cần gửi lại ảnh.",
    ),
  },
  {
    id: 13,
    slug: "noi-chuyen-voi-giao-vien",
    title: "Mở lời với một giáo viên bạn tin",
    summary: "Một lời nhờ cụ thể có thể bắt đầu bằng ba câu ngắn.",
    topic: "Nhờ hỗ trợ",
    format: "template",
    sources: ["UNICEF-VN"],
    know: "Tìm một người lớn tin cậy là một cách tìm hỗ trợ. Mẫu bên dưới do MoodPrint biên tập để luyện trình bày; không phải biểu mẫu của trường.",
    do: "“Em muốn nói riêng với cô/thầy. Trong những ngày gần đây, em gặp… Điều em cần lúc này là…” Bạn có thể đề nghị người lớn nghe hết trước khi bàn cách làm.",
    avoid:
      "Không cần kể mọi chi tiết trong tin đầu tiên hoặc gửi tên tất cả người liên quan vào một nhóm đông người.",
    example:
      "Mẫu: “Em thấy lo khi đến giờ ra chơi vì cặp bị giấu hai lần. Em muốn cô giúp tìm một cách để em có người đi cùng trong tuần này.”",
  },
  {
    id: 14,
    slug: "noi-chuyen-voi-nguoi-cham-soc",
    title: "Nói với người chăm sóc khi bạn còn ngại",
    summary: "Bạn được chọn thời điểm, cách kể và cả một người lớn khác.",
    topic: "Nhờ hỗ trợ",
    format: "template",
    sources: ["UNICEF-VN"],
    know: "Có thể khó mở lời với gia đình. Viết trước hoặc xin một khoảng thời gian nói riêng là những cách khởi đầu; nếu gia đình không an toàn, hãy chọn người lớn khác.",
    do: "“Con muốn nói một chuyện ở lớp. Con đang cần được nghe trước. Khi con kể xong, mình cùng nghĩ một việc có thể làm nhé.” Thử đọc mẫu rồi sửa thành cách nói của bạn.",
    avoid:
      "Không ép mình kể với một người khiến bạn sợ bị tổn hại. Không cần dùng lời lẽ thật trang trọng để câu chuyện được xem trọng.",
    example:
      "Mẫu nhắn: “Tối nay mình có thể nói chuyện riêng 10 phút không? Con hơi khó mở lời nên con đã viết ra trước.”",
  },
  {
    id: 15,
    slug: "khi-lan-dau-nho-giup-chua-hieu-qua",
    title: "Nếu lần đầu nhờ giúp chưa hiệu quả",
    summary: "Một phản hồi chưa đủ không đóng lại quyền tìm người hỗ trợ khác.",
    topic: "Nhờ hỗ trợ",
    format: "scenario",
    sources: ["UNICEF-VN"],
    know: "Bạn có thể cần thử một cách kể khác hoặc một người lớn khác. Điều đó không có nghĩa câu chuyện của bạn không đáng được nghe.",
    do: "Ghi điều bạn đã nhờ, phản hồi nhận được và việc có còn tiếp diễn không. Khi nói lại, xin một bước cụ thể hoặc một buổi nói chuyện riêng.",
    avoid:
      "Không cần nhận toàn bộ lỗi về mình vì lần đầu người lớn chưa hiểu. Nếu nguy cơ tăng, đừng chỉ chờ đến buổi hẹn sau.",
    example:
      "Mẫu: “Lần trước em đã nhờ về việc này. Hôm nay nó lại xảy ra, nên em muốn bàn một việc khác có thể thử.”",
    scenario: scenario(
      "Người đầu tiên nói “cứ bỏ qua”, nhưng việc vẫn lặp lại. Bạn có thể…",
      "Tìm một người lớn khác và kể việc đã tiếp diễn",
      "Bạn có quyền thử một kênh hỗ trợ khác và nói rõ lần nhờ trước chưa giải quyết được điều gì.",
      "Kết luận không ai có thể giúp nữa",
      "Một phản hồi không đại diện cho tất cả người hỗ trợ. Bạn có thể bắt đầu lại với người khác hoặc 111.",
      "Có thể nhờ bạn tin cậy đi cùng hoặc viết lời nhờ giúp thay vì kể ngay.",
    ),
  },
  {
    id: 16,
    slug: "nguoi-chung-kien",
    title: "Bạn chứng kiến: giúp mà vẫn giữ an toàn",
    summary: "Không cần tự đối đầu với cả nhóm để đứng về phía một người bạn.",
    topic: "Người chứng kiến",
    format: "scenario",
    sources: ["UNICEF-VN"],
    know: "Bạn có thể hỗ trợ người bị nhắm đến bằng một kết nối riêng và tìm người lớn. Không quay hoặc chia sẻ cảnh gây tổn thương để thu hút chú ý.",
    do: "Nếu an toàn, hỏi riêng “Bạn muốn mình đi cùng tìm cô không?”. Ghi điều chính bạn thấy, không thêm suy đoán về động cơ hoặc kể thay cảm xúc của bạn ấy.",
    avoid:
      "Không hứa giữ bí mật tuyệt đối nếu bạn lo có người đang gặp nguy hiểm. Không đặt mình vào chỗ bị tấn công để chứng tỏ tình bạn.",
    example:
      "Mẫu lời chứng do MoodPrint soạn: “Mình thấy việc xảy ra ở cửa lớp; phần trước đó mình không có mặt.”",
    scenario: scenario(
      "Bạn thấy bạn mình bị gây khó dễ trong nhóm chat. Cách hỗ trợ là…",
      "Nhắn riêng hỏi thăm và cùng tìm người lớn",
      "Một lời hỏi riêng có thể giảm cảm giác cô đơn, đồng thời để người bạn có lựa chọn về cách nhờ hỗ trợ.",
      "Chuyển ảnh chụp sang mọi nhóm để bênh bạn",
      "Chuyển tiếp có thể làm nội dung gây hại lan rộng và khiến bạn ấy mất kiểm soát thông tin.",
      "Bạn có thể bắt đầu bằng một lời hỏi thăm, không cần tự giải quyết toàn bộ việc.",
    ),
  },
  {
    id: 17,
    slug: "khi-chua-chac",
    title: "Chưa chắc chuyện gì đã xảy ra",
    summary:
      "“Mình chưa rõ” là một thông tin có ích, không phải một lỗi trong câu chuyện.",
    topic: "Nhận biết",
    format: "quiz",
    sources: ["STOP-DEFINITION"],
    know: "Đánh giá dấu hiệu cần bối cảnh về việc lặp lại, quyền lực và hành vi. Bạn không phải đoán thay những phần chưa nhìn thấy.",
    do: "Chia trang ghi chú thành: mình trực tiếp thấy; người khác kể; mình đang suy nghĩ; câu hỏi còn lại. Dùng chính những nhãn này khi nhờ người lớn giúp.",
    avoid:
      "Đừng tự đi hỏi dồn người đang khiến bạn sợ để điền cho đủ chỗ trống. Bạn có thể giữ thông tin chưa rõ.",
    example:
      "Mẫu: “Mình nghe tiếng cười sau lưng, nhưng không biết mọi người nói về điều gì. Mình thấy khó chịu và muốn tìm hiểu với người lớn.”",
    quiz: quiz(
      "Bạn không nhớ ngày chính xác. Nên ghi gì?",
      [
        "Chọn một ngày nghe có vẻ đúng",
        "Để “chưa rõ”, thêm khoảng thời gian nếu nhớ",
        "Không được ghi lại nữa",
      ],
      1,
      "Ghi mức độ chắc chắn giúp giữ câu chuyện trung thực. Không nhớ chính xác không ngăn bạn tìm hỗ trợ.",
    ),
  },
  {
    id: 18,
    slug: "chon-nguoi-tin-cay",
    title: "Chọn một người lớn bạn thấy an toàn",
    summary:
      "Không có một người phù hợp cho mọi tình huống; bạn được chọn lại.",
    topic: "Nhờ hỗ trợ",
    format: "quiz",
    sources: ["UNICEF-VN"],
    know: "Người bạn chọn có thể là giáo viên, người chăm sóc hoặc một người lớn khác. Không bắt buộc đó phải là người gần bạn nhất về quan hệ.",
    do: "Tự hỏi: mình có thể nói mà không sợ bị hại không; người đó có thời gian nghe không; họ có thể giúp tìm bước tiếp theo không? Ghi một lựa chọn dự phòng.",
    avoid:
      "Không đưa thông tin liên hệ hoặc chuyện riêng lên không gian công khai để tìm bất kỳ người lạ nào nhận giúp.",
    example:
      "Danh sách do MoodPrint gợi ý: người nói chuyện đầu tiên; người dự phòng; một câu mình muốn bắt đầu. Có thể chỉ dùng tên gọi dễ nhớ.",
    quiz: quiz(
      "Nếu chưa thấy an toàn để kể với phụ huynh, bạn có thể…",
      [
        "Chọn giáo viên hoặc người lớn khác mà mình tin",
        "Bắt buộc phải kể phụ huynh trước",
        "Chỉ nhờ người lạ trong nhóm công khai",
      ],
      0,
      "Bạn có lựa chọn về người hỗ trợ. Khi gia đình không phải kênh an toàn, hãy tìm một người lớn an toàn khác.",
    ),
  },
  {
    id: 19,
    slug: "tom-tat-trung-tinh",
    title: "Viết một tóm tắt dễ hiểu",
    summary: "Đặt hành vi, thời điểm và điều cần giúp cạnh nhau.",
    topic: "Nhờ hỗ trợ",
    format: "template",
    sources: ["STOP-REPORT"],
    know: "Ghi ngày, giờ và mô tả sự việc giúp người đọc theo dõi diễn biến. Mẫu trình bày sau là gợi ý biên tập của MoodPrint, không xác minh hay kết luận trách nhiệm.",
    do: "Viết bốn ý: việc đã thấy; thời gian biết hoặc chưa rõ; ảnh hưởng với mình; điều muốn được giúp. Dùng “mình nhìn thấy” và “mình nghe kể” cho đúng nguồn.",
    avoid:
      "Tránh từ “luôn luôn”, “tất cả” nếu bạn chưa có thông tin. Không biến suy đoán danh tính thành sự thật trong bản nháp.",
    example:
      "Mẫu: “Trong nhóm bài tập tối thứ Ba có tin nhắn gọi mình bằng tên xúc phạm. Mình không muốn vào nhóm nữa. Mình muốn cô cùng xem và giúp mình tham gia bài tập an toàn.”",
  },
  {
    id: 20,
    slug: "tam-dung-khi-lo-lang",
    title: "Cho mình một khoảng nghỉ khi lo lắng",
    summary:
      "Một khoảng nghỉ nhỏ và một người ở bên có thể là bước đầu hôm nay.",
    topic: "Chăm sóc bản thân",
    format: "guide",
    sources: ["UNICEF-VN"],
    know: "Việc bị làm tổn thương online có thể ảnh hưởng tới cảm giác và sinh hoạt. Trang này là gợi ý sinh hoạt do MoodPrint biên tập, không phải đánh giá sức khỏe tâm thần.",
    do: "Chọn một việc nhẹ phù hợp: uống nước, ngồi ở nơi yên, tắt thông báo một lúc hoặc nhắn cho người mình tin. Bạn có thể dừng bài đọc bất cứ lúc nào.",
    avoid:
      "Không ép mình phải bình tĩnh ngay để được giúp. Nếu bạn đang không an toàn hoặc có ý nghĩ làm hại bản thân, hãy tìm người lớn gần đó và trợ giúp trực tiếp ngay.",
    example:
      "Lời nhắn mẫu: “Mình đang thấy quá tải. Bạn có thể ngồi cùng mình một lúc trong khi mình tìm cô không?”",
  },
  {
    id: 21,
    slug: "tong-dai-111",
    title: "Tổng đài 111 tại Việt Nam",
    summary:
      "Một kênh chính thức về bảo vệ trẻ em, không cần qua bản nháp MoodPrint.",
    topic: "Nhờ hỗ trợ",
    format: "faq",
    sources: ["VN-111"],
    know: "Tổng đài Quốc gia bảo vệ trẻ em 111 hoạt động 24/24 và miễn phí cước gọi, tư vấn theo thông tin chính thức. Kênh này tiếp nhận thông tin về nguy cơ và hành vi xâm hại trẻ em.",
    do: "Bạn chủ động bấm liên kết gọi trên trang Hỗ trợ ngay hoặc mở tongdai111.vn. Nếu có thể, kể điều đang xảy ra, bạn đang ở đâu và điều cần giúp; không cần phải có hồ sơ đầy đủ.",
    avoid:
      "Đừng hiểu rằng lưu một bản nháp trong MoodPrint đã liên hệ 111. Ứng dụng không gọi tự động và không có người trực hỗ trợ qua màn hình này.",
    example:
      "Câu chuẩn bị do MoodPrint soạn: “Em muốn nhờ hỗ trợ về một việc khiến em thấy không an toàn. Em có thể kể từ đâu?”",
  },
  {
    id: 22,
    slug: "theo-doi-sau-khi-nho-giup",
    title: "Sau khi nhờ giúp: hẹn xem lại một bước",
    summary: "Ghi điều đã thử, kết quả bạn quan sát và điều vẫn cần hỗ trợ.",
    topic: "Nhờ hỗ trợ",
    format: "checklist",
    sources: ["UNICEF-VN"],
    know: "Tìm hỗ trợ có thể là nhiều cuộc trò chuyện. Theo dõi trong MoodPrint chỉ là tự ghi nhận; dấu hoàn thành không xác nhận rằng nhà trường đã xử lý hay bạn đã an toàn.",
    do: "Chọn ngày tự xem lại, viết việc đã thực hiện và điều thay đổi. Nếu muốn, xin người lớn một lúc để trao đổi lại. Nếu chưa tốt hơn, chọn một bước khác cùng họ.",
    avoid:
      "Không để một ngày hẹn ngăn bạn tìm giúp ngay khi nguy cơ tăng. MoodPrint không gửi nhắc lịch hoặc theo dõi thay người lớn.",
    example:
      "Ghi chú mẫu: “Mình đã nói với cô vào thứ Hai. Hai ngày sau chưa có tin nhắn mới; mình vẫn lo giờ ra chơi và muốn bàn thêm.”",
  },
  {
    id: 23,
    slug: "chon-buoc-an-toan",
    title: "Chọn một bước an toàn cho hôm nay",
    summary: "Thử nhận ra lựa chọn có hỗ trợ và tránh phải tự đối đầu.",
    topic: "Đe dọa",
    format: "quiz",
    sources: ["VN-111"],
    know: "Bạn có thể chọn một bước đủ nhỏ để làm hôm nay. Kế hoạch trên màn hình không thay trợ giúp trực tiếp khi có nguy hiểm.",
    do: "Chọn điều phù hợp với hiện tại: tìm người đi cùng, chuẩn bị một lời nhờ hoặc rời chỗ không an toàn nếu làm được. Không cần hoàn thành cả một danh sách.",
    avoid:
      "Không chọn việc buộc bạn gặp riêng người đe dọa hoặc tiếp tục ở chỗ nguy hiểm để thu thập thông tin.",
    example:
      "Ví dụ do MoodPrint soạn: “Hôm nay mình chỉ cần nhờ cô đi cùng ra cổng. Việc ghi chép mình có thể để sau.”",
    quiz: quiz(
      "Bạn thấy nguy cơ đang xảy ra. Bước nào phù hợp nhất?",
      [
        "Hoàn thành mọi trường của hồ sơ trước",
        "Tìm nơi an toàn và người lớn có thể giúp ngay",
        "Hẹn người đe dọa nói chuyện riêng",
      ],
      1,
      "An toàn và trợ giúp trực tiếp được ưu tiên. Hồ sơ có thể ghi sau; không cần đi qua một biểu mẫu mới được giúp.",
    ),
  },
  {
    id: 24,
    slug: "bao-ve-ban-be-online",
    title: "Giúp bạn trên mạng mà không lan nội dung gây hại",
    summary:
      "Ủng hộ riêng, hỏi điều bạn ấy muốn và cùng tìm người có thể giúp.",
    topic: "Người chứng kiến",
    format: "quiz",
    sources: ["UNICEF-VN"],
    know: "Một người bạn có thể cần được lắng nghe hơn là có thêm người xem nội dung gây tổn thương. Hỏi ý kiến bạn ấy trước khi chia sẻ thông tin để giúp.",
    do: "Nhắn một lời ngắn, đề nghị đi cùng tìm người lớn hoặc giúp tìm mục báo cáo chính thức. Nếu có nguy cơ nghiêm trọng, hãy tìm người lớn an toàn ngay.",
    avoid:
      "Không biến câu chuyện của bạn thành bài đăng của mình. Không yêu cầu xem thêm ảnh riêng tư để tin lời bạn.",
    example:
      "Mẫu tin nhắn: “Mình đã thấy bạn đang khó chịu. Mình có thể đi cùng bạn tìm cô, hoặc ngồi nghe nếu bạn muốn.”",
    quiz: quiz(
      "Bạn định chuyển ảnh gây xấu hổ để mọi người “biết mà bênh”. Nên làm gì?",
      [
        "Chuyển rộng hơn để tăng chú ý",
        "Dừng chuyển tiếp, hỏi riêng bạn và tìm hỗ trợ phù hợp",
        "Yêu cầu bạn gửi thêm ảnh để kiểm tra",
      ],
      1,
      "Hỗ trợ không cần làm nội dung lan rộng. Một kết nối riêng giữ cho người bạn có nhiều lựa chọn hơn về câu chuyện của mình.",
    ),
  },
];

export const knowledgeArticles: KnowledgeArticle[] = entries.map((entry) => ({
  id: `KB-${String(entry.id).padStart(2, "0")}`,
  slug: entry.slug,
  title: entry.title,
  summary: entry.summary,
  topics: [entry.topic],
  ageBands: [...both],
  readMinutes: entry.format === "quiz" ? 3 : 4,
  format: entry.format,
  sections: [
    { title: "Điều cần biết", body: entry.know },
    { title: "Một bước bạn có thể thử", body: entry.do },
    { title: "Điều cần tránh", body: entry.avoid },
    { title: "Ví dụ để chuẩn bị lời của bạn", body: entry.example },
    {
      title: "Khi cần giúp ngay",
      body: "Nếu bạn đang có nguy cơ bị tổn hại, hãy ưu tiên tìm nơi an toàn và người lớn có thể giúp trực tiếp. Không cần đọc hết bài hoặc hoàn thiện hồ sơ. Trang Hỗ trợ ngay có kênh 111 tại Việt Nam.",
    },
  ],
  sourceIds: entry.sources,
  lastReviewed: "2026-11-07",
  applicability:
    "Nội dung giáo dục tiếng Việt cho học sinh 11–17 tuổi. Ví dụ, mẫu lời nói, tình huống và câu hỏi do MoodPrint biên tập, hoàn toàn giả lập. Nguồn bên dưới dùng tham khảo chủ đề; không thẩm định từng tình huống và không thay tư vấn chuyên môn.",
  scenario: entry.scenario,
  quiz: entry.quiz,
}));

export const knowledgeTopics = [
  ...new Set(knowledgeArticles.flatMap((a) => a.topics)),
];
export const formatLabels: Record<KnowledgeArticle["format"], string> = {
  guide: "Hướng dẫn",
  scenario: "Tình huống",
  quiz: "Câu hỏi ngắn",
  checklist: "Từng bước",
  template: "Mẫu lời nói",
  faq: "Hỏi đáp",
};
export function normalizeSearch(text: string) {
  return text
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/đ/g, "d")
    .replace(/Đ/g, "D")
    .toLowerCase()
    .trim();
}
export function filterKnowledge(
  articles: KnowledgeArticle[],
  filters: { query?: string; topic?: string; age?: string; format?: string },
) {
  const words = normalizeSearch(filters.query || "")
    .split(/\s+/)
    .filter(Boolean);
  return articles.filter(
    (a) =>
      (!filters.topic || a.topics.includes(filters.topic)) &&
      (!filters.age || a.ageBands.some((age) => age === filters.age)) &&
      (!filters.format || a.format === filters.format) &&
      words.every((word) =>
        normalizeSearch(
          `${a.title} ${a.summary} ${a.topics.join(" ")} ${a.sections.map((s) => s.body).join(" ")}`,
        ).includes(word),
      ),
  );
}

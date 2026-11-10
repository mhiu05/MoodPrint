import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeft,
  ArrowUpRight,
  BarChart3,
  CheckCircle2,
  Clock3,
  FileText,
  RotateCcw,
} from "lucide-react";
import { Brand } from "../../components/layout/Brand";
import {
  Badge,
  Button,
  EmptyState,
  Modal,
  Notice,
  PageHeader,
} from "../../components/ui";
import { aggregateReports, filterReports } from "./school-data";
import { useSchoolStore } from "./school-store";
import type { SchoolReport } from "../../types";
const categoryLabels: Record<string, string> = {
  online: "Trực tuyến",
  verbal: "Lời nói",
  social: "Quan hệ nhóm",
  physical: "Xô đẩy",
  other: "Khác",
};
const statusLabels: Record<string, string> = {
  new: "Mới · Demo",
  reviewing: "Đang xem xét · Demo",
  follow_up: "Theo dõi · Demo",
  closed: "Đã đóng · Demo",
};
export function SchoolPage() {
  const { id } = useParams();
  return <SchoolView key={id ?? "overview"} />;
}
function SchoolView() {
  const { id } = useParams();
  const reports = useSchoolStore((s) => s.reports);
  const update = useSchoolStore((s) => s.update);
  const reset = useSchoolStore((s) => s.reset);
  const [month, setMonth] = useState("");
  const [category, setCategory] = useState("");
  const [status, setStatus] = useState("");
  const [query, setQuery] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [saved, setSaved] = useState(false);
  const [notes, setNotes] = useState<string | null>(null);
  const [newStatus, setNewStatus] = useState("");
  const filtered = filterReports(reports, { month, category, status }).filter(
    (r) => `${r.id} ${r.summary}`.toLowerCase().includes(query.toLowerCase()),
  );
  const stats = aggregateReports(filtered);
  const report = reports.find((r) => r.id === id);
  return (
    <>
      <header className="admin-header">
        <Brand to="/demo/school" />
        <div className="actions">
          <Badge tone="amber">School Admin · Demo Data</Badge>
          <Link className="button secondary" to="/home">
            Giao diện học sinh
            <ArrowUpRight size={16} />
          </Link>
        </div>
      </header>
      <div className="admin-banner">
        Tất cả dữ liệu đều giả lập · Trường Mẫu A · Chưa kết nối trường học ·
        Không sử dụng hồ sơ cá nhân
      </div>
      <main className="admin-layout">
        {id ? (
          report ? (
            <>
              <PageHeader
                title={report.id}
                description={`${report.group} · Báo cáo mô phỏng`}
                back="/demo/school/reports"
              />
              <div className="grid-2">
                <div className="panel stack">
                  <div className="actions">
                    <Badge tone="gray">Demo Data</Badge>
                    <Badge>{categoryLabels[report.category]}</Badge>
                    <Badge tone="blue">{statusLabels[report.status]}</Badge>
                  </div>
                  <h2>Thông tin báo cáo mẫu</h2>
                  <p>{report.summary}</p>
                  <p className="muted">
                    Ngày giả định: {report.date.split("-").reverse().join("/")}
                    <br />
                    Vai trò phụ trách: {report.handledByRole}
                  </p>
                  <Notice>
                    Dữ liệu này được tạo riêng cho School Admin Demo. Việc cập
                    nhật không thay đổi hồ sơ học sinh và không gửi thông báo.
                  </Notice>
                </div>
                <form
                  className="panel"
                  onSubmit={(e) => {
                    e.preventDefault();
                    update({
                      ...report,
                      status: (newStatus ||
                        report.status) as SchoolReport["status"],
                      notes: notes ?? report.notes,
                    });
                    setSaved(true);
                  }}
                >
                  <h2 style={{ marginBottom: 22 }}>Cập nhật xử lý mô phỏng</h2>
                  <div className="field">
                    <label htmlFor="admin-status">Trạng thái demo</label>
                    <select
                      id="admin-status"
                      value={newStatus || report.status}
                      onChange={(e) => {
                        setNewStatus(e.target.value);
                        setSaved(false);
                      }}
                    >
                      {Object.entries(statusLabels).map(([key, label]) => (
                        <option value={key} key={key}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="field">
                    <label htmlFor="admin-notes">Ghi chú xử lý giả lập</label>
                    <textarea
                      id="admin-notes"
                      value={notes ?? report.notes}
                      onChange={(e) => {
                        setNotes(e.target.value);
                        setSaved(false);
                      }}
                      placeholder="Ví dụ: chuẩn bị buổi lắng nghe trong kịch bản demo."
                    />
                  </div>
                  <Button type="submit">Lưu trạng thái demo</Button>
                  {saved && (
                    <div style={{ marginTop: 16 }}>
                      <Notice>
                        Đã cập nhật dữ liệu demo cục bộ. Chưa có ai được liên
                        hệ.
                      </Notice>
                    </div>
                  )}
                </form>
              </div>
              <section className="panel" style={{ marginTop: 22 }}>
                <h2>Diễn biến mẫu</h2>
                <ol>
                  <li>Bản báo cáo tổng hợp được tạo từ dữ liệu giả lập.</li>
                  <li>
                    Vai trò {report.handledByRole.toLowerCase()} được gán trong
                    kịch bản.
                  </li>
                  <li>Trạng thái hiện tại: {statusLabels[report.status]}.</li>
                </ol>
              </section>
            </>
          ) : (
            <EmptyState
              title="Không tìm thấy báo cáo mẫu"
              action={
                <Link to="/demo/school" className="button secondary">
                  Về School Demo
                </Link>
              }
            />
          )
        ) : (
          <>
            <PageHeader
              title="Góc nhìn nhà trường"
              description="Khám phá cách một trường có thể theo dõi và hỗ trợ. Mọi số liệu dưới đây đều là dữ liệu mẫu."
              action={
                <Button variant="secondary" onClick={() => setConfirm(true)}>
                  <RotateCcw size={16} />
                  Đặt lại demo
                </Button>
              }
            />
            <div className="admin-nav">
              <Link to="/demo/school" className="button secondary">
                <BarChart3 size={17} />
                Tổng quan
              </Link>
              <Link to="/demo/school/reports" className="button ghost">
                <FileText size={17} />
                Báo cáo mẫu
              </Link>
            </div>
            <section className="admin-filters" aria-label="Bộ lọc dữ liệu demo">
              <div className="field">
                <label htmlFor="month">Khoảng thời gian mẫu</label>
                <select
                  id="month"
                  value={month}
                  onChange={(e) => setMonth(e.target.value)}
                >
                  <option value="">3 tháng giả định</option>
                  <option value="2026-09">Tháng 9/2026</option>
                  <option value="2026-10">Tháng 10/2026</option>
                  <option value="2026-11">Tháng 11/2026</option>
                </select>
              </div>
              <div className="field">
                <label htmlFor="category">Loại sự việc mẫu</label>
                <select
                  id="category"
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                >
                  <option value="">Tất cả chủ đề</option>
                  {Object.entries(categoryLabels).map(([key, label]) => (
                    <option value={key} key={key}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="status">Trạng thái demo</label>
                <select
                  id="status"
                  value={status}
                  onChange={(e) => setStatus(e.target.value)}
                >
                  <option value="">Tất cả trạng thái</option>
                  {Object.entries(statusLabels).map(([key, label]) => (
                    <option value={key} key={key}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
            </section>
            <div className="admin-kpis">
              {[
                { title: "Báo cáo mẫu", value: stats.total, Icon: FileText },
                {
                  title: "Đang xem xét",
                  value: stats.statuses.reviewing,
                  Icon: Clock3,
                },
                {
                  title: "Theo dõi tiếp",
                  value: stats.statuses.follow_up,
                  Icon: BarChart3,
                },
                {
                  title: "Đã đóng trong demo",
                  value: stats.statuses.closed,
                  Icon: CheckCircle2,
                },
              ].map(({ title, value, Icon }) => (
                <div className="admin-kpi" key={title}>
                  <Icon size={20} />
                  <strong>{value}</strong>
                  <p>{title}</p>
                  <small className="muted">Dữ liệu mô phỏng</small>
                </div>
              ))}
            </div>
            <div className="grid-2">
              <section className="panel">
                <div className="heading-row">
                  <h2>Nhóm sự việc</h2>
                  <Badge tone="gray">Giả lập</Badge>
                </div>
                <div style={{ marginTop: 18 }}>
                  {Object.entries(stats.categories).map(([key, count]) => (
                    <div className="chart-bar-row" key={key}>
                      <span>{categoryLabels[key]}</span>
                      <div className="chart-bar">
                        <span
                          style={{
                            width: `${stats.total ? (count / stats.total) * 100 : 0}%`,
                          }}
                        />
                      </div>
                      <span>{count}</span>
                    </div>
                  ))}
                </div>
              </section>
              <section className="panel admin-chart">
                <div className="heading-row">
                  <h2>Diễn biến theo tháng</h2>
                  <Badge tone="gray">Giả lập</Badge>
                </div>
                <svg
                  viewBox="0 0 360 150"
                  role="img"
                  aria-label={`Số báo cáo mẫu tháng 9: ${stats.months["2026-09"]}, tháng 10: ${stats.months["2026-10"]}, tháng 11: ${stats.months["2026-11"]}`}
                >
                  <path
                    d="M20 120H340M20 70H340M20 20H340"
                    stroke="#e5eee8"
                    strokeWidth="1"
                  />
                  <polyline
                    points={Object.values(stats.months)
                      .map((count, i) => `${30 + i * 150},${120 - count * 5}`)
                      .join(" ")}
                    fill="none"
                    stroke="#33856b"
                    strokeWidth="3"
                  />
                  {Object.values(stats.months).map((count, i) => (
                    <g key={i}>
                      <circle
                        cx={30 + i * 150}
                        cy={120 - count * 5}
                        r="5"
                        fill="#33856b"
                      />
                      <text
                        x={30 + i * 150}
                        y={104 - count * 5}
                        textAnchor="middle"
                        fill="#355c4e"
                        fontSize="13"
                      >
                        {count}
                      </text>
                    </g>
                  ))}
                </svg>
                <div className="chart-legend">
                  <span>Tháng 9: {stats.months["2026-09"]}</span>
                  <span>Tháng 10: {stats.months["2026-10"]}</span>
                  <span>Tháng 11: {stats.months["2026-11"]}</span>
                </div>
              </section>
            </div>
            <section className="panel" style={{ marginTop: 25 }}>
              <div className="heading-row">
                <h2>Danh sách báo cáo demo</h2>
                <Badge tone="gray">{filtered.length} bản ghi giả lập</Badge>
              </div>
              <div className="field" style={{ marginTop: 20 }}>
                <label htmlFor="admin-search">Tìm báo cáo mẫu</label>
                <input
                  id="admin-search"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Mã báo cáo hoặc mô tả…"
                />
              </div>
              {filtered.length ? (
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>Mã báo cáo · Demo</th>
                      <th>Chủ đề</th>
                      <th>Nhóm mẫu</th>
                      <th>Trạng thái</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((r) => (
                      <tr key={r.id}>
                        <td>
                          <Link to={`/demo/school/reports/${r.id}`}>
                            {r.id}
                          </Link>
                          <p className="caption">
                            {r.date.split("-").reverse().join("/")}
                          </p>
                        </td>
                        <td>{categoryLabels[r.category]}</td>
                        <td>{r.group}</td>
                        <td>
                          <Badge
                            tone={r.status === "closed" ? "green" : "blue"}
                          >
                            {statusLabels[r.status]}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <EmptyState
                  title="Không có báo cáo mẫu phù hợp"
                  action={
                    <Button
                      variant="secondary"
                      onClick={() => {
                        setQuery("");
                        setMonth("");
                        setCategory("");
                        setStatus("");
                      }}
                    >
                      Xóa bộ lọc
                    </Button>
                  }
                />
              )}
            </section>
            <Link to="/home" className="back-link" style={{ marginTop: 25 }}>
              <ArrowLeft size={16} />
              Quay lại giao diện học sinh
            </Link>
          </>
        )}
        <Modal
          open={confirm}
          onClose={() => setConfirm(false)}
          title="Đặt lại dữ liệu School Demo?"
        >
          <p>
            Chỉ khôi phục 48 báo cáo giả lập trong khu nhà trường. Hồ sơ học
            sinh không thay đổi.
          </p>
          <div className="actions end">
            <Button variant="secondary" onClick={() => setConfirm(false)}>
              Hủy
            </Button>
            <Button
              onClick={() => {
                reset();
                setConfirm(false);
              }}
            >
              Khôi phục School Demo
            </Button>
          </div>
        </Modal>
      </main>
    </>
  );
}

export function AgeFields({
  year,
  confirmed,
  currentYear,
  onYear,
  onConfirmed,
  readOnly = false,
  prefix = "age",
}: {
  year: string;
  confirmed: boolean;
  currentYear: number;
  onYear: (year: string) => void;
  onConfirmed: (value: boolean) => void;
  readOnly?: boolean;
  prefix?: string;
}) {
  return (
    <>
      <label htmlFor={`${prefix}-birth-year`}>Năm sinh</label>
      <input
        id={`${prefix}-birth-year`}
        type="number"
        inputMode="numeric"
        autoComplete="bday-year"
        min={1900}
        max={currentYear}
        required
        readOnly={readOnly}
        value={year}
        onChange={(event) => {
          onYear(event.target.value);
          onConfirmed(false);
        }}
      />
      <label className="real-age-confirmation">
        <input
          type="checkbox"
          checked={confirmed}
          onChange={(event) => onConfirmed(event.target.checked)}
        />
        <span>Tôi xác nhận mình đã đủ 18 tuổi.</span>
      </label>
      <p>
        Năm sinh và xác nhận do bạn tự khai báo, không phải xác minh bằng giấy
        tờ tùy thân.
      </p>
    </>
  );
}

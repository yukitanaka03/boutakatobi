// 仮ページ：FR-1 の遷移確認用。中身は FR-3・4・6 で作り替える
type SearchParams = Promise<Record<string, string | string[] | undefined>>;

export default async function FarewellResultsPage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const params = await searchParams;
  return (
    <main style={{ maxWidth: 560, margin: "0 auto", padding: "48px 16px" }}>
      <h1>候補（準備中）</h1>
      <p>受け取った入力条件：</p>
      <pre style={{ background: "#fff", padding: 16, borderRadius: 8 }}>
        {JSON.stringify(params, null, 2)}
      </pre>
    </main>
  );
}

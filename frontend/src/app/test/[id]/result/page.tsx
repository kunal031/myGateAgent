import ExamResult from "@/features/exam/ExamResult";

export default async function ResultPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ExamResult examId={Number(id)} />;
}

// The session id comes from the URL and the paper is fetched at runtime,
// so there is nothing to prerender. Route segment config has to live in a
// server component, which is why the client part sits in ExamRunner.
export const instant = false;

import ExamRunner from "@/features/exam/ExamRunner";

export default async function ExamPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ExamRunner examId={Number(id)} />;
}

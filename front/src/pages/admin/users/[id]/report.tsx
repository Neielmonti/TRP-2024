import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import { withAuth } from "~/components/withAuth";

interface ReportEntry {
  question_text: string;
  answer: string;
}

const UserReport = () => {
  const router = useRouter();
  const { id } = router.query;
  const [report, setReport] = useState<ReportEntry[]>([]);
  const [userName, setUserName] = useState<string | null>(null);
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;

  useEffect(() => {
    if (!router.isReady || !id) return;
    console.log("Fetching report for ID:", id);

    fetch(`${process.env.NEXT_PUBLIC_API_URL}/users/report?user_id=${id}`, {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then(r => r.json())
      .then(data => {
        console.log("Received data:", data);
        if (!data || !data.questions_answered) return;

        setUserName(data.user?.name + " " + data.user?.lastname + " (" + data.user?.DNI + ") " ?? "Usuario sin nombre");

        const transformed: ReportEntry[] = data.questions_answered.map((qa: any) => {
          const question = qa.question;
          const answer = qa.answer;

          let question_text = "Pregunta no disponible";
          let answer_text = "Respuesta no disponible";

          if (question) {
            question_text = question.body ?? "Sin texto de pregunta";

            if (question.type === "Choice" && answer?.selectedOption != null) {
              const index = parseInt(answer.selectedOption);
              const option = question.options?.[index];
              answer_text = option?.body ?? "Opción no encontrada";
            } else if (answer?.body) {
              answer_text = answer.body;
            }
          } else if (answer?.body) {
            answer_text = answer.body;
          }

          return { question_text, answer: answer_text };
        });

        setReport(transformed);
      });
  }, [router.isReady, id]);

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <h1 className="text-3xl font-bold mb-2 text-center">Reporte de Respuestas</h1>
      {userName && <h2 className="text-xl text-gray-600 mb-6 text-center">Usuario: {userName}</h2>}

      <div className="mb-4">
        <button
          onClick={() => router.push("/admin/users")}
          className="bg-red-500 text-white px-4 py-2 rounded hover:bg-gray-600"
        >
          Volver a adm usuarios
        </button>
      </div>

      <div className="space-y-4">
        {report.map((r, i) => (
          <div key={i} className="bg-white shadow rounded-lg p-4 border border-gray-200">
            <div className="text-sm text-gray-500 mb-1">Pregunta {i + 1}</div>
            <p className="font-medium text-gray-800">{r.question_text}</p>
            <div className="mt-2">
              <span className="text-sm font-semibold text-gray-600">Respuesta:</span>
              <p className="text-gray-700 bg-gray-50 rounded p-2 mt-1">{r.answer}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default withAuth(UserReport);

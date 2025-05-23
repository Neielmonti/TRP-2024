import { type NextPage } from "next";
import Link from "next/link";
import { Fragment, useEffect, useState, useCallback } from "react";
import { useRouter } from "next/router";
import { withAuth } from "~/components/withAuth";
import { useUnits } from "~/hooks/useUnits";
import { useQuestions } from "~/hooks/useQuestions";
import { useCompletedQuestions } from "~/hooks/useCompletedQuestions";

import {
  ActiveBookSvg,
  LockedBookSvg,
  CheckmarkSvg,
  LockSvg,
  StarSvg,
  GuidebookSvg,
} from "~/components/Svgs";
import { TopBar } from "~/components/TopBar";
import { BottomBar } from "~/components/BottomBar";
import { RightBar } from "~/components/RightBar";
import { LeftBar } from "~/components/LeftBar";
import { LoginScreen, useLoginScreen } from "~/components/LoginScreen";

// --- Interfaces ---
interface Unit {
  _id: string;
  title: string;
  level: number;
  backgroundColor?: string;
  borderColor?: string;
  textColor?: string;
  tiles: Array<{
    questionId: string;
    type: string;
    description: string;
    exp: number;
  }>;
}

interface Question {
  _id: string;
  type: string;
  body: string;
  exp: number;
  unit_id: string;
}

// --- Transform to tile ---
const questionToTile = (q: Question) => ({
  questionId: q._id,
  type: q.type === "Choice" ? "book" : "star",
  description: q.body,
  exp: q.exp,
});

const mapQuestionsToUnits = (units: Omit<Unit, "tiles">[], questions: Question[]): Unit[] =>
  units.map((u) => ({
    ...u,
    tiles: questions
      .filter((q) => q.unit_id === u._id)
      .map(questionToTile),
  }));

// --- Compute status based on backend progress ---
type TileStatus = "LOCKED" | "ACTIVE" | "COMPLETE";

const tileStatus = (
  tile: { questionId: string },
  completed: string[],
  unitTiles: { questionId: string }[]
): TileStatus => {
  if (completed.includes(tile.questionId)) return "COMPLETE";
  // First uncompleted question in this unit
  const firstUncompleted = unitTiles.find((t) => !completed.includes(t.questionId));
  return firstUncompleted?.questionId === tile.questionId ? "ACTIVE" : "LOCKED";
};

// --- Render one unit ---
const UnitSection = ({
  unit,
  completed,
}: {
  unit: Unit;
  completed: string[];
}) => {
  const router = useRouter();
  const [selectedTile, setSelectedTile] = useState<number | null>(null);
  const closeTooltip = useCallback(() => setSelectedTile(null), []);

  useEffect(() => {
    const onScroll = () => setSelectedTile(null);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <section className="mb-12">
      <article className={["max-w-2xl text-white sm:rounded-xl", unit.backgroundColor || "bg-[#58cc02]"].join(" ")}>
        <header className="flex items-center justify-between p-4">
          <div>
            <h2 className="text-2xl font-bold">Unidad {unit.level}</h2>
            <p className="text-lg">{unit.title}</p>
          </div>
          <Link
            href={`https://duolingo.com/guidebook/${unit.level}`}
            className={["flex items-center gap-3 p-3 rounded-2xl border-2 border-b-4 transition hover:text-gray-100", unit.borderColor || "border-[#46a302]"].join(" ")}
          >
            <GuidebookSvg />
            <span className="sr-only">Guidebook</span>
          </Link>
        </header>
      </article>

      <div className="relative flex flex-col items-center gap-4">
        {unit.tiles.map((tile, i) => {
          const status = tileStatus(tile, completed, unit.tiles);
          return (
            <Fragment key={tile.questionId}>
              <div className="relative -mb-4 h-[93px] w-[98px]">
                <button
                  onClick={() => router.push(`/lesson?questionId=${tile.questionId}`)}
                  disabled={status !== "ACTIVE"}
                  className={[
                    "absolute m-3 rounded-full p-4 border-b-8",
                    status === "COMPLETE"
                      ? "border-yellow-500 bg-yellow-400"
                      : status === "ACTIVE"
                      ? `${unit.borderColor || "border-[#46a302]"} ${unit.backgroundColor || "bg-[#58cc02]"}`
                      : "border-gray-300 bg-gray-200",
                  ].join(" ")}
                >
                  {status === "COMPLETE" ? (
                    <CheckmarkSvg />
                  ) : status === "ACTIVE" ? (
                    tile.type === "book" ? <ActiveBookSvg /> : <StarSvg />
                  ) : tile.type === "book" ? (
                    <LockedBookSvg />
                  ) : (
                    <LockSvg />
                  )}
                </button>
              </div>
            </Fragment>
          );
        })}
      </div>
    </section>
  );
};

// --- Main page ---
const Learn: NextPage = () => {
  const { loginScreenState, setLoginScreenState } = useLoginScreen();
  const [scrollY, setScrollY] = useState(0);
  useEffect(() => {
    const onScroll = () => setScrollY(window.scrollY);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const unitsData = useUnits();
  const questionsData = useQuestions();
  const completed = useCompletedQuestions();

  if (unitsData.length === 0 || questionsData.length === 0) {
    return <div className="p-6">Cargando contenido...</div>;
  }

  const unitsWithTiles = mapQuestionsToUnits(unitsData, questionsData);
  const sortedUnits = [...unitsWithTiles].sort((a, b) => a.level - b.level);

  return (
    <>
      <TopBar backgroundColor="bg-[#58cc02]" borderColor="border-[#46a302]" />
      <LeftBar selectedTab="Learn" />

      <div className="flex justify-center gap-6 pt-14 p-6">
        <div className="w-full max-w-2xl">
          {sortedUnits.map((unit) => (
            <UnitSection key={unit._id} unit={unit} completed={completed} />
          ))}
          {/* espacio extra al final para permitir scroll completo */}
          <div className="h-32" />
        </div>
        <RightBar />
      </div>

      <BottomBar selectedTab="Learn" />
      <LoginScreen loginScreenState={loginScreenState} setLoginScreenState={setLoginScreenState} />
    </>
  );
};

export default withAuth(Learn);

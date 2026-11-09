import { createContext, useContext } from "react";

export type Lang = "en" | "ar";

const AR: Record<string, string> = {
  "Overview": "نظرة عامة", "Forecast & Scoring": "التنبؤ والتقييم", "Executive Matrix": "المصفوفة التنفيذية",
  "Geospatial": "الخريطة الجغرافية", "Interventions": "التدخلات", "Announcements": "الإعلانات",
  "Engagement Log": "سجل التواصل", "Register": "سجل الفرص", "Ask Precast": "اسأل بريكاست",
  "Ontology & Graph": "الأنطولوجيا والرسم المعرفي", "Data & Integrations": "البيانات والتكامل",
  "Active opportunities": "الفرص النشطة", "Indicative pipeline": "خط الأنابيب الإرشادي",
  "Risk-weighted expected value": "القيمة المتوقعة المرجحة بالمخاطر", "Executive interventions": "التدخلات التنفيذية",
  "Overdue open actions": "إجراءات متأخرة", "Due in next 30 days": "مستحقة خلال 30 يوماً", "Blocked actions": "إجراءات متعثرة",
  "Not verified in 30+ days": "غير محدثة منذ 30 يوماً", "Forecast by quarter": "التنبؤ حسب الربع",
  "Pipeline by stage": "خط الأنابيب حسب المرحلة", "Outlook distribution": "توزيع التوقعات",
  "Pipeline by domain": "خط الأنابيب حسب المجال", "Needs leadership attention": "تتطلب اهتمام القيادة",
  "Biggest probability moves (14 days)": "أكبر تغيرات الاحتمال (14 يوماً)", "Near-term milestones": "المراحل القريبة",
  "Win probability": "احتمال الفوز", "Expected close": "الإغلاق المتوقع", "Search": "بحث",
  "Strategic Intelligence Hub": "مركز الذكاء الاستراتيجي", "Predict. Forecast. Precast.": "تنبّأ. توقّع. بريكاست.",
  "Commit": "مؤكد", "Best case": "أفضل حالة", "Pipeline": "خط الأنابيب", "Weighted": "مرجح",
  "Draft briefing memo": "صياغة مذكرة إحاطة", "Draft sponsor email": "صياغة بريد للراعي", "Discussion": "النقاش",
  "Ask": "اسأل", "Load tracker": "تحميل المتتبع", "Download template": "تنزيل القالب",
};

export const LangCtx = createContext<Lang>("en");
export function useT() {
  const lang = useContext(LangCtx);
  return (s: string) => (lang === "ar" ? AR[s] ?? s : s);
}

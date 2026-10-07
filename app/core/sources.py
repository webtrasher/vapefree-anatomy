"""Библиография таймлайнов восстановления.

Каждое утверждение в модулях органов ссылается на ключ из этого словаря.
Приложение носит информационно-мотивационный характер и не заменяет
консультацию врача.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    key: str
    org: str
    title: str
    detail: str
    url: str


SOURCES: dict[str, Source] = {
    s.key: s
    for s in (
        Source(
            key="who-cessation",
            org="ВОЗ",
            title="Tobacco: Health benefits of smoking cessation",
            detail=(
                "Сводные сроки оздоровления после прекращения употребления никотина: "
                "ЧСС и АД снижаются в первые сутки, функция лёгких растёт в течение 1–9 месяцев."
            ),
            url="https://www.who.int/news-room/fact-sheets/detail/tobacco",
        ),
        Source(
            key="cdc-benefits",
            org="CDC",
            title="Benefits of Quitting Smoking",
            detail=(
                "Таймлайн CDC: 20 минут — падение ЧСС и АД; 2–12 недель — улучшение "
                "кровообращения и функции лёгких; 1–9 месяцев — восстановление ресничек "
                "мерцательного эпителия."
            ),
            url="https://www.cdc.gov/tobacco/quit_smoking/how_to_quit/benefits/index.htm",
        ),
        Source(
            key="nhs-quit",
            org="NHS",
            title="What happens when you quit smoking",
            detail="Пошаговый таймлайн: 48 часов — восстановление вкуса и обоняния; 1 год — риск ИБС вдвое ниже.",
            url="https://www.nhs.uk/live-well/quit-smoking/what-happens-when-you-quit-smoking/",
        ),
        Source(
            key="aha-endothelial",
            org="American Heart Association",
            title="Endothelial function and arterial stiffness after smoking cessation",
            detail=(
                "Никотин вызывает дисфункцию эндотелия и повышение жёсткости артерий; "
                "показатели улучшаются в течение 2–12 недель воздержания."
            ),
            url="https://www.heart.org/en/healthy-living/healthy-lifestyle/quit-smoking-tobacco",
        ),
        Source(
            key="brody-nachr",
            org="Brody et al., Arch Gen Psychiatry, 2006",
            title="Cigarette smoking saturates brain alpha4beta2 nicotinic acetylcholine receptors",
            detail=(
                "Плотность никотиновых рецепторов α4β2 у курящих выше нормы; при воздержании "
                "она возвращается к уровню некурящих в течение 3–4 недель."
            ),
            url="https://pubmed.ncbi.nlm.nih.gov/16894063/",
        ),
        Source(
            key="benowitz-pk",
            org="Benowitz, Annu Rev Pharmacol Toxicol",
            title="Nicotine addiction and pharmacokinetics",
            detail=(
                "Период полувыведения никотина ≈ 2 часа, котинина ≈ 16–20 часов; "
                "полная элиминация никотина и котинина занимает около 72 часов."
            ),
            url="https://pubmed.ncbi.nlm.nih.gov/8713430/",
        ),
        Source(
            key="sleep-nicotine",
            org="Jaehne et al., Sleep Med Rev",
            title="Nicotine: effects on sleep and daytime performance",
            detail=(
                "Никотин увеличивает латентность сна, подавляет быстрые фазы и фрагментирует "
                "сон; архитектура сна восстанавливается недели-месяцы после отказа."
            ),
            url="https://pubmed.ncbi.nlm.nih.gov/23352092/",
        ),
        Source(
            key="pg-vg-airway",
            org="Пульмонология / исследования аэрозоля ЭСДН",
            title="Airway epithelial irritation from propylene glycol and vegetable glycerin",
            detail=(
                "Пропиленгликоль и глицерин в аэрозоле вызывают раздражение и липоидное "
                "воспаление эпителия дыхательных путей и альвеол. В отличие от табачного дыма "
                "угарный газ и смолы отсутствуют, поэтому оксигенация страдает меньше, "
                "а воспаление дыхательных путей разрешается быстрее."
            ),
            url="https://pubmed.ncbi.nlm.nih.gov/31353851/",
        ),
        Source(
            key="habit-loop",
            org="Поведенческая психология",
            title="Oral/hand-to-mouth ritual and habit extinction",
            detail=(
                "Вейпинг — это не только никотин, но и орально-моторный ритуал. "
                "Угасание автоматизированной привычки занимает в среднем 30–90 дней."
            ),
            url="https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5315489/",
        ),
    )
}


def citation(keys: tuple[str, ...]) -> list[Source]:
    """Вернуть объекты источников по ключам, пропуская неизвестные."""
    return [SOURCES[k] for k in keys if k in SOURCES]

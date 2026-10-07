"""A dose unit is read in Russian, however the course was written.

The form offers «таб», «капс», «кап», «мл», «шт», but the server accepts any string: a course
made by a script or by an older client carries «tablet», and the Russian screen used to print
«По 1 tablet». Reading is what is translated — the course keeps what was written, so nothing is
lost and the next save is still the owner's own word.
"""

from web.helpers import ru_dose_unit


class TestRuDoseUnit:
    def test_english_units_become_the_russian_ones(self):
        assert ru_dose_unit("tablet") == "таб"
        assert ru_dose_unit("tablets") == "таб"
        assert ru_dose_unit("capsule") == "капс"
        assert ru_dose_unit("drops") == "кап"
        assert ru_dose_unit("ml") == "мл"
        assert ru_dose_unit("pcs") == "шт"
        assert ru_dose_unit("mg") == "мг"
        assert ru_dose_unit("g") == "г"
        assert ru_dose_unit("kg") == "кг"

    def test_case_and_surrounding_spaces_do_not_matter(self):
        assert ru_dose_unit("  Tablet  ") == "таб"
        assert ru_dose_unit("ML") == "мл"

    def test_russian_units_stay_as_written(self):
        assert ru_dose_unit("таб") == "таб"
        assert ru_dose_unit("капс") == "капс"
        assert ru_dose_unit("мл") == "мл"
        assert ru_dose_unit("шт.") == "шт."

    def test_an_unknown_unit_is_left_alone(self):
        # A unit nobody knows is better shown as it was written than guessed at.
        assert ru_dose_unit("ampoule") == "ampoule"
        assert ru_dose_unit("почка") == "почка"

    def test_only_the_whole_unit_is_matched(self):
        # «мг/мл» is two units and has its own short form; matching inside a word would turn
        # «г» inside «мг» into «г».
        assert ru_dose_unit("мг/мл") == "мг/мл"
        assert ru_dose_unit("mg/ml") == "мг/мл"
        assert ru_dose_unit("мг") == "мг"

    def test_nothing_is_not_a_string(self):
        assert ru_dose_unit(None) == ""
        assert ru_dose_unit("") == ""
        assert ru_dose_unit(7) == ""

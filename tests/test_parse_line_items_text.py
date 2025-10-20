from pdf_scraper.items import parse_line_items


def test_parse_two_asbach_items_from_text():
    sample = (
        "18 18 CS006 184111\n"
        "816095011117\n"
        "ASBACH BRANDY-FILLED CHOCOLATE\n"
        "SQUARES LARGE\n"
        "6/8.8 OZ $86.94 $1,564.92\n"
        "\n"
        "18 18 CS006 184121\n"
        "816095011216\n"
        "ASBACH LARGE CHERRIES WITH BRANDY\n"
        "6/7.05 OZ $77.94 $1,402.92\n"
    )

    items = parse_line_items(sample)
    assert len(items) == 2

    it1, it2 = items

    assert it1.item == "184111"
    assert it1.upc == "816095011117"
    assert it1.pack_size == "6/8.8 OZ"
    assert it1.price == 86.94
    assert round(it1.extended_price, 2) == 1564.92

    assert it2.item == "184121"
    assert it2.upc == "816095011216"
    assert it2.pack_size == "6/7.05 OZ"
    assert it2.price == 77.94
    assert round(it2.extended_price, 2) == 1402.92


def test_parse_hyphenated_item_id():
    sample = (
        "4 4 CS002 138915-2\n"
        "4008100150157\n"
        "HENGSTENBERG MILDESSA SAUERKRAUT WITH\n"
        "WINE LARGE TIN 2PK\n"
        "2/342 OZ $62.98 $251.92\n"
    )

    items = parse_line_items(sample)
    assert len(items) == 1
    it = items[0]
    assert it.item == "138915-2"
    assert it.upc == "4008100150157"
    assert it.pack_size == "2/342 OZ"
    assert it.price == 62.98
    assert round(it.extended_price, 2) == 251.92

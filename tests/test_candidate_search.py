"""Kandidatenliste: Suche, Filter, Sortierung, Seiten."""


def _seed(admin):
    lv = {e['code']: e['id'] for e in admin.get('/api/catalogs/language-level').get_json()['entries']}
    st = {e['code']: e['id'] for e in admin.get('/api/catalogs/candidate-status').get_json()['entries']}
    people = [('Citra', 'SHK', 'B1', 'EXAM_PREPARATION'), ('agus', 'Elektro', 'A1', 'LANGUAGE_COURSE'),
              ('Budi 100%', 'Elektro', 'A2', 'PROSPECT'), ('Dewi', 'SHK', None, None)]
    ids = {}
    for name, fach, level, status in people:
        ids[name] = admin.post('/api/candidates', json={
            'name': name, 'fach': fach, 'email': f'{name[:4].lower()}@example.org',
            'current_level_id': lv.get(level), 'status_id': st.get(status)}).get_json()['id']
    return lv, st, ids


def _names(res):
    assert res.status_code == 200, res.get_json()
    return [i['name'] for i in res.get_json()['items']]


def test_standard_sortierung_nach_name_ohne_gross_klein(as_user):
    admin = as_user('root_admin')
    _seed(admin)
    assert _names(admin.get('/api/candidates')) == ['agus', 'Budi 100%', 'Citra', 'Dewi']
    assert _names(admin.get('/api/candidates?sort=-name')) == ['Dewi', 'Citra', 'Budi 100%', 'agus']


def test_sortierung_nach_niveau_und_status_leere_zuletzt(as_user):
    admin = as_user('root_admin')
    _seed(admin)
    assert _names(admin.get('/api/candidates?sort=level')) == ['agus', 'Budi 100%', 'Citra', 'Dewi']
    assert _names(admin.get('/api/candidates?sort=-status')) == ['Citra', 'agus', 'Budi 100%', 'Dewi']


def test_suche_in_name_nummer_und_mail(as_user):
    admin = as_user('root_admin')
    _seed(admin)
    assert _names(admin.get('/api/candidates?q=CIT')) == ['Citra']
    assert _names(admin.get('/api/candidates?q=K-00002')) == ['agus']
    assert _names(admin.get('/api/candidates?q=dewi@')) == ['Dewi']


def test_suche_behandelt_prozent_als_zeichen(as_user):
    admin = as_user('root_admin')
    _seed(admin)
    assert _names(admin.get('/api/candidates?q=%25')) == ['Budi 100%']


def test_filter(as_user):
    admin = as_user('root_admin')
    lv, st, _ = _seed(admin)
    assert _names(admin.get('/api/candidates?fach=SHK')) == ['Citra', 'Dewi']
    assert _names(admin.get(f'/api/candidates?level_id={lv["A1"]}')) == ['agus']
    assert _names(admin.get(f'/api/candidates?status_id={st["PROSPECT"]}&fach=Elektro')) == ['Budi 100%']


def test_seiten(as_user):
    admin = as_user('root_admin')
    _seed(admin)
    body = admin.get('/api/candidates?per_page=3&page=2').get_json()
    assert (body['total'], body['page'], [i['name'] for i in body['items']]) == (4, 2, ['Dewi'])
    assert admin.get('/api/candidates?per_page=500').status_code == 400
    assert admin.get('/api/candidates?sort=geheim').status_code == 400


def test_letzte_bewertung_in_der_liste(as_user):
    admin = as_user('root_admin')
    _, _, ids = _seed(admin)
    admin.post('/api/ratings', json={'trainee_id': ids['Dewi'], 'r_practical': 8, 'r_reliability': 7, 'r_motivation': 9})
    items = admin.get('/api/candidates?sort=-last_rating').get_json()['items']
    assert items[0]['name'] == 'Dewi' and items[0]['last_rating_at'] is not None

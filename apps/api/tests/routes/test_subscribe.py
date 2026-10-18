from uuid import uuid4

from app.models.subscribers import Subscriber


def _subscriber(db_session, filters=None) -> Subscriber:
    sub = Subscriber(
        email="reader@example.com",
        filters=filters or {},
        confirmed=True,
        confirm_token=str(uuid4()),
        unsubscribe_token=str(uuid4()),
    )
    db_session.add(sub)
    db_session.commit()
    return sub


def test_preferences_save_and_return_date_posted_choice(test_client, db_session):
    sub = _subscriber(db_session, {"party": "D"})

    res = test_client.put(
        f"/api/subscribe/preferences/{sub.unsubscribe_token}",
        json={"filters": {"party": "D", "freshness": "30"}},
    )
    prefs = test_client.get(f"/api/subscribe/preferences/{sub.unsubscribe_token}").json()

    assert res.status_code == 200
    assert prefs["filters"] == {"party": "D", "freshness": "30"}


def test_confirmed_subscriber_resubscribing_saves_date_posted_choice(test_client, db_session):
    _subscriber(db_session)

    res = test_client.post(
        "/api/subscribe",
        json={"email": "reader@example.com", "filters": {"freshness": "older_30"}},
    )

    assert res.json() == {"message": "Subscription filters updated."}
    db_session.expire_all()
    assert db_session.query(Subscriber).one().filters == {"freshness": "older_30"}


def test_unknown_date_posted_choice_is_rejected(test_client, db_session):
    sub = _subscriber(db_session)

    res = test_client.put(
        f"/api/subscribe/preferences/{sub.unsubscribe_token}",
        json={"filters": {"freshness": "14"}},
    )

    assert res.status_code == 422

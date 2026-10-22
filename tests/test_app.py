from copy import deepcopy
from urllib.parse import quote

import pytest


def test_root_redirects_to_frontend(client):
    # Arrange
    url = "/"

    # Act
    response = client.get(url, follow_redirects=False)

    # Assert
    assert response.status_code == 307
    assert response.headers["location"] == "/static/index.html"


def test_frontend_is_served(client):
    # Arrange
    url = "/static/index.html"

    # Act
    response = client.get(url)

    # Assert
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Mergington High School" in response.text


def test_get_activities_returns_populated_and_empty_activities(client, activity_data):
    # Arrange
    expected = deepcopy(activity_data)

    # Act
    response = client.get("/activities")

    # Assert
    assert response.status_code == 200
    assert response.json() == expected


@pytest.mark.parametrize("activity_name", ["Chess Club", "Art Club"])
def test_signup_adds_one_participant_and_preserves_other_data(client, activity_data, activity_name):
    # Arrange
    email = "new+student@mergington.edu"
    url = f"/activities/{quote(activity_name, safe='')}/signup"
    expected = deepcopy(activity_data)
    expected[activity_name]["participants"].append(email)

    # Act
    response = client.post(url, params={"email": email})
    activities_response = client.get("/activities")

    # Assert
    assert response.status_code == 200
    assert response.json() == {"message": f"Signed up {email} for {activity_name}"}
    assert activities_response.status_code == 200
    assert activities_response.json() == expected
    assert activities_response.json()[activity_name]["participants"].count(email) == 1


@pytest.mark.parametrize("method, action", [("POST", "signup"), ("DELETE", "unregister")])
def test_unknown_activity_returns_404_without_mutation(client, activity_data, method, action):
    # Arrange
    expected = deepcopy(activity_data)
    url = f"/activities/Unknown%20Club/{action}"
    email = "student@mergington.edu"

    # Act
    response = client.request(method, url, params={"email": email})
    activities_response = client.get("/activities")

    # Assert
    assert response.status_code == 404
    assert response.json() == {"detail": "Activity not found"}
    assert activities_response.status_code == 200
    assert activities_response.json() == expected


def test_duplicate_signup_returns_400_without_mutation(client, activity_data):
    # Arrange
    expected = deepcopy(activity_data)
    email = activity_data["Chess Club"]["participants"][0]

    # Act
    response = client.post("/activities/Chess%20Club/signup", params={"email": email})
    activities_response = client.get("/activities")

    # Assert
    assert response.status_code == 400
    assert response.json() == {"detail": "Student already signed up for this activity"}
    assert activities_response.status_code == 200
    assert activities_response.json() == expected


@pytest.mark.parametrize("email", ["michael@mergington.edu", "daniel@mergington.edu"])
def test_unregister_removes_only_selected_participant(client, activity_data, email):
    # Arrange
    expected = deepcopy(activity_data)
    expected["Chess Club"]["participants"].remove(email)
    initial_count = len(activity_data["Chess Club"]["participants"])
    initial_spots = activity_data["Chess Club"]["max_participants"] - initial_count

    # Act
    response = client.delete("/activities/Chess%20Club/unregister", params={"email": email})
    activities_response = client.get("/activities")

    # Assert
    assert response.status_code == 200
    assert response.json() == {"message": f"Unregistered {email} from Chess Club"}
    assert activities_response.status_code == 200
    assert activities_response.json() == expected
    activity = activities_response.json()["Chess Club"]
    assert len(activity["participants"]) == initial_count - 1
    assert activity["max_participants"] - len(activity["participants"]) == initial_spots + 1


def test_unregister_last_participant_leaves_empty_list(client, activity_data):
    # Arrange
    email = "artist@mergington.edu"
    client.post("/activities/Art%20Club/signup", params={"email": email}).raise_for_status()
    expected = deepcopy(activity_data)

    # Act
    response = client.delete("/activities/Art%20Club/unregister", params={"email": email})
    activities_response = client.get("/activities")

    # Assert
    assert response.status_code == 200
    assert response.json() == {"message": f"Unregistered {email} from Art Club"}
    assert activities_response.status_code == 200
    assert activities_response.json() == expected
    assert activities_response.json()["Art Club"]["participants"] == []


def test_unregister_absent_participant_returns_404_without_mutation(client, activity_data):
    # Arrange
    expected = deepcopy(activity_data)
    email = "absent@mergington.edu"

    # Act
    response = client.delete("/activities/Chess%20Club/unregister", params={"email": email})
    activities_response = client.get("/activities")

    # Assert
    assert response.status_code == 404
    assert response.json() == {"detail": "Student is not signed up for this activity"}
    assert activities_response.status_code == 200
    assert activities_response.json() == expected


@pytest.mark.parametrize("method, action", [("POST", "signup"), ("DELETE", "unregister")])
def test_missing_email_returns_422_without_mutation(client, activity_data, method, action):
    # Arrange
    expected = deepcopy(activity_data)
    url = f"/activities/Chess%20Club/{action}"

    # Act
    response = client.request(method, url)
    activities_response = client.get("/activities")

    # Assert
    assert response.status_code == 422
    assert any(error["loc"] == ["query", "email"] for error in response.json()["detail"])
    assert activities_response.status_code == 200
    assert activities_response.json() == expected


def test_participant_can_register_again_after_unregistering(client, activity_data):
    # Arrange
    email = "returning@mergington.edu"
    params = {"email": email}
    expected_registered = deepcopy(activity_data)
    expected_registered["Art Club"]["participants"].append(email)

    # Act
    signup_response = client.post("/activities/Art%20Club/signup", params=params)
    activities_response = client.get("/activities")

    # Assert
    assert signup_response.status_code == 200
    assert activities_response.status_code == 200
    assert activities_response.json() == expected_registered

    # Arrange
    expected_unregistered = deepcopy(activity_data)

    # Act
    unregister_response = client.delete("/activities/Art%20Club/unregister", params=params)
    activities_response = client.get("/activities")

    # Assert
    assert unregister_response.status_code == 200
    assert activities_response.status_code == 200
    assert activities_response.json() == expected_unregistered

    # Arrange
    signup_url = "/activities/Art%20Club/signup"

    # Act
    second_signup_response = client.post(signup_url, params=params)
    activities_response = client.get("/activities")

    # Assert
    assert second_signup_response.status_code == 200
    assert second_signup_response.json() == {"message": f"Signed up {email} for Art Club"}
    assert activities_response.status_code == 200
    assert activities_response.json() == expected_registered
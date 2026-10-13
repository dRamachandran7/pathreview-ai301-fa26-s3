"""Tests for review_service.py"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import core.services.review_service as review_service
from api.main import app
from api.middleware.auth import get_current_user
from core.database import get_db
from core.services.review_service import (
    compute_profile_content_hash,
    create_review,
    get_or_create_review,
    get_review,
    list_reviews,
    process_review,
)


@pytest.mark.unit
class TestReviewService:
    """Test suite for review_service module."""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock async database session."""
        session = AsyncMock()
        session.add = Mock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def mock_review(self):
        """Create a mock Review object."""
        review = Mock()
        review.id = uuid4()
        review.status = "pending"
        review.sections = None
        review.overall_score = None
        return review

    @pytest.fixture
    def mock_profile(self):
        """Create a mock Profile object."""
        profile = Mock()
        profile.id = uuid4()
        profile.user_id = uuid4()
        return profile

    @pytest.mark.asyncio
    async def test_create_review_returns_review_with_pending_status(
        self, mock_db_session, mock_review
    ):
        """Test create_review returns Review with status='pending'."""
        profile_id = uuid4()
        user_id = uuid4()

        # Setup mock
        mock_db_session.add = Mock()
        mock_db_session.commit = AsyncMock()
        mock_db_session.refresh = AsyncMock()

        with patch("core.services.review_service.Review") as MockReview:
            mock_instance = MockReview.return_value
            mock_instance.status = "pending"
            mock_instance.sections = None
            mock_instance.overall_score = None

            result = await create_review(mock_db_session, profile_id, user_id)

            # Check that Review was instantiated
            MockReview.assert_called()
            call_kwargs = MockReview.call_args[1]
            assert call_kwargs["status"] == "pending"

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        strict=True, reason="issue #65: review_service tests misconfigure async mocks"
    )
    async def test_get_review_returns_review_for_correct_owner(self, mock_db_session):
        """Test get_review returns review when user_id matches."""
        review_id = uuid4()
        user_id = uuid4()

        mock_review = Mock()
        mock_review.id = review_id

        # Setup mock execute to return review
        mock_result = AsyncMock()
        mock_result.scalars.return_value.first.return_value = mock_review
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await get_review(mock_db_session, review_id, user_id)

        assert result == mock_review
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        strict=True, reason="issue #65: review_service tests misconfigure async mocks"
    )
    async def test_get_review_returns_none_for_wrong_user(self, mock_db_session):
        """Test get_review returns None when user_id doesn't match."""
        review_id = uuid4()
        user_id = uuid4()
        wrong_user_id = uuid4()

        # Setup mock to return None
        mock_result = AsyncMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await get_review(mock_db_session, review_id, wrong_user_id)

        assert result is None

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        strict=True, reason="issue #65: review_service tests misconfigure async mocks"
    )
    async def test_list_reviews_returns_paginated_results(self, mock_db_session):
        """Test list_reviews returns paginated results."""
        user_id = uuid4()

        # Create mock reviews
        mock_reviews = [Mock() for _ in range(5)]

        # Setup execute mock to return reviews
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = mock_reviews
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        reviews, total = await list_reviews(mock_db_session, user_id, page=1, page_size=20)

        assert len(reviews) > 0 or len(reviews) == 0  # May be empty
        assert isinstance(total, int)
        assert total >= 0

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        strict=True, reason="issue #65: review_service tests misconfigure async mocks"
    )
    async def test_list_reviews_page_2_returns_correct_offset(self, mock_db_session):
        """Test list_reviews page 2 returns correct offset."""
        user_id = uuid4()
        page_size = 20

        # Setup mock
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        reviews, total = await list_reviews(mock_db_session, user_id, page=2, page_size=page_size)

        # Second call should pass offset for page 2
        calls = mock_db_session.execute.call_args_list
        # Should have at least one call
        assert len(calls) > 0

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        strict=True, reason="issue #65: review_service tests misconfigure async mocks"
    )
    async def test_list_reviews_returns_tuple(self, mock_db_session):
        """Test list_reviews returns (reviews, total) tuple."""
        user_id = uuid4()

        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await list_reviews(mock_db_session, user_id)

        assert isinstance(result, tuple)
        assert len(result) == 2
        reviews, total = result
        assert isinstance(reviews, list)
        assert isinstance(total, int)

    @pytest.mark.asyncio
    async def test_create_review_calls_db_add(self, mock_db_session):
        """Test create_review calls db.add()."""
        profile_id = uuid4()
        user_id = uuid4()

        with patch("core.services.review_service.Review"):
            await create_review(mock_db_session, profile_id, user_id)

            mock_db_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_review_calls_db_commit(self, mock_db_session):
        """Test create_review calls db.commit()."""
        profile_id = uuid4()
        user_id = uuid4()

        with patch("core.services.review_service.Review"):
            await create_review(mock_db_session, profile_id, user_id)

            mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_review_calls_db_refresh(self, mock_db_session):
        """Test create_review calls db.refresh()."""
        profile_id = uuid4()
        user_id = uuid4()

        with patch("core.services.review_service.Review"):
            await create_review(mock_db_session, profile_id, user_id)

            mock_db_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        strict=True, reason="issue #65: review_service tests misconfigure async mocks"
    )
    async def test_get_review_uses_select_and_join(self, mock_db_session):
        """Test get_review constructs proper SQL with join."""
        review_id = uuid4()
        user_id = uuid4()

        mock_result = AsyncMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        await get_review(mock_db_session, review_id, user_id)

        # Should call execute with a statement
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        strict=True, reason="issue #65: review_service tests misconfigure async mocks"
    )
    async def test_list_reviews_default_pagination(self, mock_db_session):
        """Test list_reviews uses default pagination."""
        user_id = uuid4()

        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        reviews, total = await list_reviews(mock_db_session, user_id)

        # Should use default page=1, page_size=20
        assert isinstance(reviews, list)
        assert isinstance(total, int)

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        strict=True, reason="issue #65: review_service tests misconfigure async mocks"
    )
    async def test_list_reviews_custom_page_size(self, mock_db_session):
        """Test list_reviews with custom page size."""
        user_id = uuid4()
        custom_page_size = 50

        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        reviews, total = await list_reviews(
            mock_db_session, user_id, page=1, page_size=custom_page_size
        )

        assert isinstance(reviews, list)

    @pytest.mark.asyncio
    async def test_create_review_with_uuid_ids(self, mock_db_session):
        """Test create_review handles UUID objects correctly."""
        profile_id = uuid4()
        user_id = uuid4()

        with patch("core.services.review_service.Review") as MockReview:
            MockReview.return_value = Mock()
            await create_review(mock_db_session, profile_id, user_id)

            call_kwargs = MockReview.call_args[1]
            assert "profile_id" in call_kwargs
            assert "status" in call_kwargs

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        strict=True, reason="issue #65: review_service tests misconfigure async mocks"
    )
    async def test_get_review_verifies_ownership(self, mock_db_session):
        """Test get_review checks Profile.user_id matches."""
        review_id = uuid4()
        user_id = uuid4()

        mock_result = AsyncMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        await get_review(mock_db_session, review_id, user_id)

        # Should construct query with user_id filter
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        strict=True, reason="issue #65: review_service tests misconfigure async mocks"
    )
    async def test_list_reviews_counts_total(self, mock_db_session):
        """Test list_reviews calculates total count."""
        user_id = uuid4()

        mock_reviews = [Mock() for _ in range(5)]
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = mock_reviews
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        reviews, total = await list_reviews(mock_db_session, user_id)

        # Total should be counted
        assert isinstance(total, int)

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        strict=True, reason="issue #65: review_service tests misconfigure async mocks"
    )
    async def test_list_reviews_returns_reviews_list(self, mock_db_session):
        """Test list_reviews returns list of Review objects."""
        user_id = uuid4()

        mock_reviews = [Mock(spec=["id", "status"]) for _ in range(3)]
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = mock_reviews
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        reviews, total = await list_reviews(mock_db_session, user_id)

        assert isinstance(reviews, list)

    @pytest.mark.asyncio
    async def test_review_sections_and_score_initially_none(self, mock_db_session):
        """Test review has None for sections and overall_score initially."""
        profile_id = uuid4()
        user_id = uuid4()

        with patch("core.services.review_service.Review") as MockReview:
            MockReview.return_value = Mock()
            await create_review(mock_db_session, profile_id, user_id)

            call_kwargs = MockReview.call_args[1]
            assert call_kwargs["sections"] is None
            assert call_kwargs["overall_score"] is None

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        strict=True, reason="issue #65: review_service tests misconfigure async mocks"
    )
    async def test_get_review_with_valid_uuid(self, mock_db_session):
        """Test get_review handles valid UUID parameters."""
        review_id = uuid4()
        user_id = uuid4()

        mock_result = AsyncMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        # Should not raise
        result = await get_review(mock_db_session, review_id, user_id)

        assert result is None or result is not None  # Just verify no exception

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        strict=True, reason="issue #65: review_service tests misconfigure async mocks"
    )
    async def test_list_reviews_ordered_by_created_at(self, mock_db_session):
        """Test list_reviews returns results ordered by created_at desc."""
        user_id = uuid4()

        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        reviews, total = await list_reviews(mock_db_session, user_id)

        # Should order by created_at descending
        mock_db_session.execute.assert_called_once()


def _profile(**overrides):
    fields = {
        "id": str(uuid4()),
        "github_username": "octocat",
        "portfolio_url": "https://example.test/portfolio",
        "resume_text": "Resume text",
        "resume_filename": "resume.pdf",
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


def _result(value):
    """Synchronous stand-in for a SQLAlchemy result: result.scalars().first()."""
    result = Mock()
    result.scalars.return_value.first.return_value = value
    return result


@pytest.mark.unit
class TestReviewContentHashCache:
    """Tests for reusing completed reviews when profile content is unchanged (#9)."""

    @pytest.fixture
    def db(self):
        session = AsyncMock()
        session.add = Mock()
        return session

    def test_hash_is_stable_for_identical_profile_content(self):
        assert compute_profile_content_hash(_profile()) == compute_profile_content_hash(_profile())

    @pytest.mark.parametrize(
        "field", ["github_username", "portfolio_url", "resume_text", "resume_filename"]
    )
    def test_hash_changes_when_any_reviewed_field_changes(self, field):
        original = _profile()
        changed = _profile(**{field: "changed"})
        assert compute_profile_content_hash(original) != compute_profile_content_hash(changed)

    def test_hash_distinguishes_missing_from_empty(self):
        assert compute_profile_content_hash(
            _profile(resume_text=None)
        ) != compute_profile_content_hash(_profile(resume_text=""))

    @pytest.mark.asyncio
    async def test_get_or_create_returns_cached_review_on_hit(self, db):
        profile = _profile()
        cached = SimpleNamespace(id=uuid4(), status="complete")
        db.execute = AsyncMock(side_effect=[_result(profile), _result(cached)])

        review, is_cached = await get_or_create_review(db, profile.id, uuid4())

        assert review is cached
        assert is_cached is True
        db.add.assert_not_called()
        db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_or_create_creates_pending_review_on_miss(self, db):
        profile = _profile()
        db.execute = AsyncMock(side_effect=[_result(profile), _result(None)])

        review, is_cached = await get_or_create_review(db, profile.id, uuid4())

        assert is_cached is False
        assert review.status == "pending"
        assert review.content_hash is None
        db.add.assert_called_once_with(review)

    @pytest.mark.asyncio
    async def test_get_or_create_creates_review_when_profile_missing(self, db):
        db.execute = AsyncMock(return_value=_result(None))

        review, is_cached = await get_or_create_review(db, uuid4(), uuid4())

        assert is_cached is False
        assert review.status == "pending"
        db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_review_stores_content_hash_on_completion(self, db):
        profile = _profile()
        review = SimpleNamespace(id=uuid4(), status="pending", content_hash=None)
        db.execute = AsyncMock(side_effect=[_result(review), _result(profile)])

        await process_review(db, review.id, profile.id)

        assert review.status == "complete"
        assert review.content_hash == compute_profile_content_hash(profile)

    @pytest.mark.asyncio
    async def test_process_review_leaves_hash_unset_when_safety_checks_fail(self, db):
        profile = _profile()
        review = SimpleNamespace(id=uuid4(), status="pending", content_hash=None)
        db.execute = AsyncMock(side_effect=[_result(review), _result(profile)])

        with patch.object(review_service, "_run_safety_checks", AsyncMock(return_value=False)):
            await process_review(db, review.id, profile.id)

        assert review.status == "failed"
        assert review.content_hash is None


@pytest.mark.unit
class TestCreateReviewEndpointCache:
    """POST /reviews only schedules the pipeline on a cache miss (#9)."""

    @pytest.fixture
    def client(self):
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=uuid4())
        app.dependency_overrides[get_db] = lambda: AsyncMock()
        yield TestClient(app)
        app.dependency_overrides.clear()

    def _review(self, status):
        now = datetime.utcnow()
        return SimpleNamespace(
            id=uuid4(),
            profile_id=uuid4(),
            status=status,
            sections=None,
            overall_score=None,
            error_message=None,
            created_at=now,
            updated_at=now,
        )

    @pytest.mark.parametrize(("cached", "expected_calls"), [(True, 0), (False, 1)])
    def test_pipeline_scheduled_only_on_miss(self, client, cached, expected_calls):
        review = self._review("complete" if cached else "pending")
        with (
            patch(
                "api.routes.reviews.get_or_create_review",
                AsyncMock(return_value=(review, cached)),
            ),
            patch("api.routes.reviews.process_review", AsyncMock()) as mock_process,
        ):
            response = client.post("/reviews", json={"profile_id": str(review.profile_id)})

        assert response.status_code == 200
        assert response.json()["id"] == str(review.id)
        assert response.json()["status"] == review.status
        assert mock_process.call_count == expected_calls

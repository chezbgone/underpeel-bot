import aiohttp
import pytest_asyncio
import pytest

import cogs.underpeel.peelo as peelo
from models.peelo import Episode10Eligibility, Episode9Eligibility, NotEligible
from models.valorant import ImmortalPlus, RiotId, SimpleRank


@pytest_asyncio.fixture()
async def http_session():
    return aiohttp.ClientSession()


@pytest.mark.asyncio
async def test_e9_eligibility(http_session):
    _, actual, _ = await peelo.get_matches_info(
        http_session, RiotId("chezbgone", "hask")
    )
    expected = Episode9Eligibility(
        a1=66, a2=35, a3=31, peak=SimpleRank(tier="Gold", division=3)
    )
    assert actual == expected


@pytest.mark.asyncio
async def test_e10_eligibility(http_session):
    _, eligibility, _ = await peelo.get_matches_info(
        http_session, RiotId("Liberty", "80085")
    )
    if not isinstance(eligibility, Episode10Eligibility):
        raise ValueError(eligibility)


@pytest.mark.asyncio
async def test_e9_overrides_e10(http_session):
    _, actual, _ = await peelo.get_matches_info(http_session, RiotId("snoww", "hater"))
    expected = Episode9Eligibility(
        a1=122, a2=128, a3=133, peak=SimpleRank(tier="Diamond", division=3)
    )
    assert actual == expected


@pytest.mark.asyncio
async def test_immortal_plus(http_session):
    _, actual, _ = await peelo.get_matches_info(
        http_session, RiotId("Orangers", "2131")
    )
    match actual:
        case None | NotEligible():
            raise ValueError(actual)
    expected = ImmortalPlus(name="Immortal 1")
    assert actual.peak == expected

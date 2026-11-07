package com.konecto.series76.data

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ApiResultTest {
    private fun server(status: Int, code: String?) = ApiResult.Failure(FailureKind.Server(status, code), "m")

    @Test fun turnInProgressIsRetryable() = assertTrue(server(409, "turn_in_progress").retryable)
    @Test fun otherConflictIsNot() = assertFalse(server(409, "other").retryable)
    @Test fun unauthorizedIsNot() = assertFalse(server(401, "unauthorized").retryable)
    @Test fun serverErrorIs() = assertTrue(server(503, null).retryable)
    @Test fun networkIs() = assertTrue(ApiResult.Failure(FailureKind.Network, "m").retryable)
}

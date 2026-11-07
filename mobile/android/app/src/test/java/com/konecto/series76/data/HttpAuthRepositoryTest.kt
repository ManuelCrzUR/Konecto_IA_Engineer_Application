package com.konecto.series76.data

import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.io.File

class HttpAuthRepositoryTest {
    private val server = MockWebServer()
    private lateinit var store: SessionStore
    private lateinit var dir: File
    private lateinit var auth: HttpAuthRepository

    @Before fun setUp() {
        server.start()
        dir = kotlin.io.path.createTempDirectory("auth").toFile().apply { deleteOnExit() }
        store = newStore()
        val api = ApiClient.create(
            server.url("/").toString(),
            interceptor = AuthInterceptor({ store.current?.token }, {}),
        )
        auth = HttpAuthRepository(api, store)
    }

    @After fun tearDown() = server.shutdown()

    private fun newStore() = SessionStore(
        PreferenceDataStoreFactory.create(
            scope = CoroutineScope(UnconfinedTestDispatcher() + Job()),
            produceFile = { File(dir, "auth.preferences_pb") },
        ),
    )

    @Test fun tokenIsReadFromDiskAfterProcessDeath() = runBlocking {
        store.save(AuthSession("t1", "ana@konecto.test", "user"))
        // A new process: Android restores the screen without the splash, nobody calls load().
        val restored = SessionStore(
            PreferenceDataStoreFactory.create(
                scope = CoroutineScope(UnconfinedTestDispatcher() + Job()),
                produceFile = { File(dir, "auth2.preferences_pb").also { File(dir, "auth.preferences_pb").copyTo(it) } },
            ),
        )
        assertEquals("t1", restored.token())
    }

    @Test fun tokenStaysNullAfterSignOut() = runBlocking {
        store.save(AuthSession("t1", "ana@konecto.test", "user"))
        store.clear()
        assertNull(store.token())
    }

    @Test fun loginSavesTheSession() = runBlocking {
        server.enqueue(MockResponse().setBody("""{"token":"t1","user":{"email":"ana@konecto.test","role":"user"}}"""))
        val r = auth.login("ana@konecto.test", "pw")
        assertTrue(r is ApiResult.Success)
        assertEquals("t1", store.current?.token)
        assertEquals("t1", store.session.first()?.token)
    }

    @Test fun wrongPasswordKeepsNoSession() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(401).setBody("""{"error":"invalid_credentials"}"""))
        val r = auth.login("ana@konecto.test", "bad") as ApiResult.Failure
        assertEquals("Wrong email or password", r.message)
        assertNull(store.current)
    }

    @Test fun logoutClearsLocallyAndRevokesWithTheOldToken() = runBlocking {
        store.save(AuthSession("t1", "ana@konecto.test", "user"))
        server.enqueue(MockResponse().setResponseCode(204))
        auth.logout()
        assertNull(store.current)
        assertNull(store.session.first())
        val req = server.takeRequest()
        assertEquals("/api/auth/logout", req.path)
        assertEquals("Bearer t1", req.getHeader("Authorization"))
    }

    @Test fun logoutOfflineStillClearsTheSession() = runBlocking {
        store.save(AuthSession("t1", "ana@konecto.test", "user"))
        server.shutdown() // nothing listening: the revoke call fails fast
        auth.logout()
        assertNull(store.current)
        assertNull(store.session.first())
    }
}

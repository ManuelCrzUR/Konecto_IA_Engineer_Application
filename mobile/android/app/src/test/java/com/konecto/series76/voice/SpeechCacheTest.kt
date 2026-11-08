package com.konecto.series76.voice

import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

@OptIn(ExperimentalCoroutinesApi::class)
class SpeechCacheTest {
    private fun cache(scope: kotlinx.coroutines.test.TestScope, dir: File) =
        SpeechCache(dir, StandardTestDispatcher(scope.testScheduler)) { 1_000L }

    @Test fun putThenGetRoundTripsAndLeavesNoTempFile() = runTest {
        val dir = tempCacheDir()
        val c = cache(this, dir)
        val f = c.put("k", 0, "Hello", byteArrayOf(1, 2, 3), "mp3")
        assertNotNull(f)
        assertEquals(f, c.get("k", 0, "Hello"))
        assertTrue(dir.listFiles()!!.none { it.name.endsWith(".tmp") })
    }

    @Test fun getNeverReturnsATempFile() = runTest {
        val dir = tempCacheDir()
        val c = cache(this, dir)
        val f = c.put("k", 0, "Hello", byteArrayOf(1), "mp3")!!
        f.delete()
        // A half-written temp file next to where the real one would be.
        File(dir, f.name + ".tmp").writeBytes(byteArrayOf(9, 9))
        assertNull(c.get("k", 0, "Hello"))
    }

    @Test fun cacheDirThatIsAFileIsAMissNotAnException() = runTest {
        val file = File.createTempFile("notadir", "").apply { deleteOnExit() }
        val c = cache(this, File(file, "sub"))
        assertNull(c.put("k", 0, "Hello", byteArrayOf(1), "mp3"))
        assertNull(c.get("k", 0, "Hello"))
    }
}

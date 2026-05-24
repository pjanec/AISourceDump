pls identity all failing tests in both solutions. make a tracker file where you mark each test as not fixes initially. your goal is to fix those by delegating the fixes from the same test group to developer subagent Claude Sonnet 4.6 (do not use exploration agent!) Let the subagent report (append) D:\Work\IOS-IG-SimHost-FDP-2\.dev\test-fixes.md what was tests he fixed and what was the issue. make a git commit after each subagent return if changes were made. Mark fixed tests as fixed in the tracker file.
Re-run the tests to check for regression and update the failed test tracker accordingly.
Continue delegating next failing test group to another sub-agent Claude Sonnet 4.6.
Keep delegating untill all test groups are all green. Before finishing, make sure the solution compiles and all tests are green, otherwise keep updating tracker delegating fixes.


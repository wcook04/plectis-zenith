Experience from earlier testing sessions on other functions. For each, you see the inputs that were tried, then each hidden bug that those inputs MISSED, with the buggy code and an input that exposes it.

### HumanEval/1: Input to this function is a string containing multiple groups of nested parentheses. Your goal is to separate those group into separate strings and return the list of those. Separate groups are balanced (each open brace is properly closed) 
Inputs tried: ('   ',); ('()()',); (' ( ) ',); ('((()))',); ('(()())(())',)
Bugs exposed: 1 of 1

### HumanEval/106: Implement the function f that takes n as a parameter, and returns a list of size n, such that the value of the element at index i is the factorial of i if i is even or the sum of numbers from 1 to i otherwise. i starts from 1. the factorial
Inputs tried: (0,); (7,); (8,); (10,); (1000,)
Bugs exposed: 1 of 1

### HumanEval/108: Write a function count_nums which takes an array of integers and returns the number of elements which has a sum of digits > 0. If a number is negative, then its first signed digit will be negative: e.g. -123 has signed digits -1, 2, and 3. 
Inputs tried: ([-12],); ([-21],); ([-123],); ([0],); ([-102],)
Bugs exposed: 1 of 1

### HumanEval/11: Input are two strings a and b consisting only of 1s and 0s. Perform binary XOR on these inputs and return result also as a string. >>> string_xor('010', '110') '100'
Inputs tried: ('', ''); ('00', '00'); ('11', '10'); ('0001', '0010'); ('1000', '0010')
Bugs exposed: 1 of 1

### HumanEval/112: Task We are given two strings s and c, you have to deleted all the characters in s that are equal to any character in c then check if the result string is palindrome. A string is called palindrome if it reads the same backward as forward. Y
Inputs tried: ('abca', 'b'); ('abc', 'abc'); ('ab', ''); ('', 'a'); ('abcde', 'ace')
Bugs exposed: 3 of 4
Missed bug:
```python
def reverse_delete(s, c):
    for i in s:
        if i in c:
            s = s.replace(i, '')
    s = str(s)
    s = s.lower()
    r = s[::-1]
    if s == r:
        return (s, True)
    return (s, False)
```
Exposing input: ('noxUJIAn', 'non')  reference -> ('xUJIA', False)  bug -> ('xujia', False)

### HumanEval/114: Given an array of integers nums, find the minimum sum of any non-empty sub-array of nums. Example minSubArraySum([2, 3, 4, 1, 2, 4]) == 1 minSubArraySum([-1, -2, -3]) == -6
Inputs tried: ([-10, 2, -10],); ([5, -10, -10],); ([2, -1, -2, -3, 1],); ([1, 0, 2],); ([-7],)
Bugs exposed: 1 of 2
Missed bug:
```python
import math

def minSubArraySum(nums):
    n = len(nums)
    min_so_far = math.inf
    min_ending_here = 0
    for i in range(n):
        min_ending_here += nums[i]
        if min_so_far > min_ending_here:
            min_so_far = min_ending_here
        if min_ending_here > 0:
            min_ending_here = 0
    return min_so_far
```
Exposing input: ([True, True, True, False, True, True],)  reference -> False  bug -> 0

### HumanEval/138: Evaluate whether the given number n can be written as the sum of exactly 4 positive even numbers Example is_equal_to_sum_even(4) == False is_equal_to_sum_even(6) == False is_equal_to_sum_even(8) == True
Inputs tried: (9,); (10,); (0,); (-2,); (100,)
Bugs exposed: 2 of 5
Missed bug:
```python
def is_equal_to_sum_even(n):
    count = 0
    for i in range(2, n):
        if i % 2 == 0:
            for j in range(2, n):
                if j % 2 == 0:
                    for k in range(2, n):
                        if k % 2 == 0:
                            for l in range(2, n):
                                if l % 2 == 0:
                                    if i + j + k + l == n:
                                        count += 1
    return count > 0
```
Exposing input: (107,)  reference -> False  bug -> False
Missed bug:
```python
def is_equal_to_sum_even(n):
    for i in range(2, n):
        for j in range(2, n):
            for k in range(2, n):
                for l in range(2, n):
                    if i + j + k + l == n and i % 2 == j % 2 == k % 2 == l % 2 == 0:
                        return True
    return False
```
Exposing input: (97,)  reference -> False  bug -> <timeout>
Missed bug:
```python
def is_equal_to_sum_even(n):
    if n < 8:
        return False
    for i in range(2, n):
        if i % 2 == 0:
            for j in range(2, n):
                if j % 2 == 0:
                    for k in range(2, n):
                        if k % 2 == 0:
                            for l in range(2, n):
                                if l % 2 == 0:
                                    if i + j + k + l == n:
                                        return True
    return False
```
Exposing input: (109,)  reference -> False  bug -> False

### HumanEval/149: Write a function that accepts a list of strings as a parameter, deletes the strings that have odd lengths from it, and returns the resulted list with a sorted order, The list is always a list of strings and never an array of numbers, and it
Inputs tried: (['bb', 'aa', 'dd', 'cc'],); (['dd', 'a', 'bb', 'ccc', 'gg', 'e', 'ffff'],); (['cd', 'ab', 'a', 'aaa', 'ab', 'b'],); (['', 'b', 'aa', '', 'c', 'bb'],); (['bbbb', 'zz', 'aa', 'cc', 'a', 'dddd', 'bb'],)
Bugs exposed: 2 of 3
Missed bug:
```python
def sorted_list_sum(lst):
    if len(lst) == 0:
        return []
    if len(lst) == 1:
        return lst[0:1]
    lst1 = []
    for i in lst:
        if len(i) % 2 == 0:
            lst1.append(i)
    lst2 = sorted(lst1, key=lambda s: (len(s), s))
    return lst2
```
Exposing input: (['a'],)  reference -> []  bug -> ['a']

### HumanEval/157: Given the lengths of the three sides of a triangle. Return True if the three sides form a right-angled triangle, False otherwise. A right-angled triangle is a triangle in which one angle is right angle or 90 degree. Example: right_angle_tri
Inputs tried: (13, 12, 5); (5, 13, 12); (6, 8, 10); (1, 1, 1); (2, 3, 4)
Bugs exposed: 1 of 2
Missed bug:
```python
def right_angle_triangle(a, b, c):
    assert isinstance(a, int)
    assert isinstance(b, int)
    assert isinstance(c, int)

    def triangle_valid(a, b, c):
        return a + b > c and a + c > b and (b + c > a)
    if not triangle_valid(a, b, c):
        return False
    if a ** 2 + b ** 2 == c ** 2 or a ** 2 + c ** 2 == b ** 2 or b ** 2 + c ** 2 == a ** 2:
        return True
    return False
```
Exposing input: (24.71115668501026, 93.15108572417166, 93.65019636949225)  reference -> False  bug -> <exc AssertionError>

### HumanEval/158: Write a function that accepts a list of strings. The list contains different words. Return the word with maximum number of unique characters. If multiple strings have maximum number of unique characters, return the one which comes first in 
Inputs tried: (['aabb', 'abcd'],); (['abc', 'aabc', 'abccc'],); (['aA', 'ab'],); (['aB', 'Ab'],); (['a!', 'bc'],)
Bugs exposed: 0 of 1
Missed bug:
```python
def find_max(words):
    unique = set()
    max_len = 0
    word = None
    for i in words:
        if len(set(i)) > max_len:
            max_len = len(set(i))
            word = i
        elif len(set(i)) == max_len:
            if i < word:
                word = i
    return word
```
Exposing input: ([''],)  reference -> ''  bug -> <exc TypeError>

### HumanEval/159: You're a hungry rabbit, and you already have eaten a certain number of carrots, but now you need to eat more carrots to complete the day's meals. you should return an array of [ total number of eaten carrots after your meals, the number of 
Inputs tried: (0, 0, 0); (5, 0, 10); (5, 6, 0); (0, 1000, 999); (1000, 999, 1000)
Bugs exposed: 1 of 2
Missed bug:
```python
def eat(number, need, remaining):
    if remaining == 0 and number < need:
        return [number, 0]
    elif remaining == 0 and number >= need:
        return [need, 0]
    elif remaining < need:
        return [number + remaining, 0]
    elif remaining >= need:
        return [number + need, remaining - need]
```
Exposing input: (999, 1, 0)  reference -> [999, 0]  bug -> [1, 0]

### HumanEval/161: You are given a string s. if s[i] is a letter, reverse its case from lower to upper or vise versa, otherwise keep it as it is. If the string contains no letters, reverse the string. The function should return the resulted string. Examples s
Inputs tried: ('aⅠ',); ('AB12',); ('中1',); ('ß1',); ('!1@',)
Bugs exposed: 1 of 1

### HumanEval/18: Find how many times a given substring can be found in the original string. Count overlaping cases. >>> how_many_times('', 'a') 0 >>> how_many_times('aaa', 'a') 3 >>> how_many_times('aaaa', 'aa') 3
Inputs tried: ('aaaaa', 'aaa'); ('abc', 'abc'); ('a.b.c', '.'); ('Aaa', 'a'); ('abc', 'd')
Bugs exposed: 3 of 3

### HumanEval/19: Input is a space-delimited string of numberals from 'zero' to 'nine'. Valid choices are 'zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight' and 'nine'. Return the string with numbers sorted from smallest to largest >>> so
Inputs tried: ('',); ('zero',); ('nine eight seven six five four three two one zero',); ('one zero three two five four seven six nine eight zero nine five one',); ('eight eight seven seven six six five five four four three three two two one one zero zero nine nine',)
Bugs exposed: 1 of 1

### HumanEval/31: Return true if a given number is prime, and false otherwise. >>> is_prime(6) False >>> is_prime(101) True >>> is_prime(11) True >>> is_prime(13441) True >>> is_prime(61) True >>> is_prime(4) False >>> is_prime(1) False
Inputs tried: (2,); (9,); (25,); (0,); (-3,)
Bugs exposed: 9 of 13
Missed bug:
```python
def is_prime(n):
    if n < 2:
        return False
    for i in range(2, n):
        if n % i == 0:
            return False
    return True
```
Exposing input: (123456791,)  reference -> True  bug -> <timeout>
Missed bug:
```python
def is_prime(n):
    if n < 2:
        return False
    if n == 2:
        return True
    for i in range(2, n):
        if n % i == 0:
            return False
    return True
```
Exposing input: (9999991,)  reference -> True  bug -> True
Missed bug:
```python
def is_prime(n):
    """*** YOUR CODE HERE ***"""
    i = 0
    for j in range(1, n):
        if n % j == 0:
            i += 1
    if i == 1:
        return True
    else:
        return False
```
Exposing input: (123456789,)  reference -> False  bug -> <timeout>

### HumanEval/35: Return maximum element in the list. >>> max_element([1, 2, 3]) 3 >>> max_element([5, 3, -5, 2, -3, 3, 9, 0, 123, 1, -10]) 123
Inputs tried: ([-5],); ([-3, -1, -2],); ([-5, -4, -3, -2],); ([-10.5, -2.5, -7.0],); ([0.1, 0.3, 0.2],)
Bugs exposed: 4 of 5
Missed bug:
```python
def max_element(l: list):
    return max([v for v in l if v != 0])
```
Exposing input: ([-2, -3, 0],)  reference -> 0  bug -> -2

### HumanEval/39: prime_fib returns n-th number that is a Fibonacci number and it's also prime. >>> prime_fib(1) 2 >>> prime_fib(2) 3 >>> prime_fib(3) 5 >>> prime_fib(4) 13 >>> prime_fib(5) 89
Inputs tried: (6,); (9,); (10,); (11,); (12,)
Bugs exposed: 1 of 1

### HumanEval/46: The Fib4 number sequence is a sequence similar to the Fibbonacci sequnece that's defined as follows: fib4(0) -> 0 fib4(1) -> 0 fib4(2) -> 2 fib4(3) -> 0 fib4(n) -> fib4(n-1) + fib4(n-2) + fib4(n-3) + fib4(n-4). Please write a function to ef
Inputs tried: (2,); (3,); (4,); (1,); (1000,)
Bugs exposed: 7 of 7

### HumanEval/5: Insert a number 'delimeter' between every two consecutive elements of input list `numbers' >>> intersperse([], 4) [] >>> intersperse([1, 2, 3], 4) [1, 4, 2, 4, 3]
Inputs tried: ([7], -3); ([1, 2], 0); ([1, 2, 3], 2); ([1, 2, 3, 4], -1); ([], 0)
Bugs exposed: 2 of 2

### HumanEval/52: Return True if all numbers in the list l are below threshold t. >>> below_threshold([1, 2, 4, 10], 100) True >>> below_threshold([1, 20, 4, 10], 5) False
Inputs tried: ([], 0); ([0], 0); ([100, -100], 1); ([5.0], 5); ([-1.5], -1)
Bugs exposed: 4 of 5
Missed bug:
```python
def below_threshold(l: list, t: int):
    return all((x < t for x in l if x >= 0))
```
Exposing input: ([-2, -4], -4)  reference -> False  bug -> True

### HumanEval/54: Check if two words have the same characters. >>> same_chars('eabcdzzzz', 'dddzzzzzzzddeddabc') True >>> same_chars('abcd', 'dddddddabc') True >>> same_chars('dddddddabc', 'abcd') True >>> same_chars('eabcd', 'dddddddabc') False >>> same_cha
Inputs tried: ('abc', 'def'); ('a', 'b'); ('', ''); ('A', 'a'); ('a b', 'ab')
Bugs exposed: 5 of 6
Missed bug:
```python
def same_chars(s0: str, s1: str):
    letters_s0 = []
    letters_s1 = []
    letters_s0.extend(s0)
    letters_s1.extend(s1)
    letters_s0 = set(letters_s0)
    letters_s1 = set(letters_s1)
    if len(letters_s0) != len(letters_s1):
        return False
    else:
        letters_s0 = list(letters_s0)
        letters_s1 = list(letters_s1)
        letters_s0.sort(key=letters_s0.count)
        letters_s1.sort(key=letters_s1.count)
    for x, y in zip(letters_s0, letters_s1):
        if x != y:
            return False
    return True
```
Exposing input: ('dog', 'odog')  reference -> True  bug -> True

### HumanEval/58: Return sorted unique common elements for two lists. >>> common([1, 4, 3, 34, 653, 2, 5], [5, 7, 1, 5, 9, 653, 121]) [1, 5, 653] >>> common([5, 3, 2, 8], [3, 2]) [2, 3]
Inputs tried: ([1, 1, 2, 3], [1, 2, 3]); ([8, 1, 10], [10, 8, 1]); ([0, -1, 2], [2, 0, -1]); ([2, 10, 11, 1], [11, 2, 10, 1]); ([[1], [2]], [[2], [3]])
Bugs exposed: 16 of 20
Missed bug:
```python
def common(l1: list, l2: list):
    l1 = sorted(l1)
    l2 = sorted(l2)
    lst = list(set(l1) & set(l2))
    lst.sort()
    return lst
```
Exposing input: ([False, None], [])  reference -> []  bug -> <exc TypeError>
Missed bug:
```python
def common(l1: list, l2: list):
    if l1 == []:
        return l2
    else:
        return sorted(list(set(l1) & set(l2)))
```
Exposing input: ([], [1])  reference -> []  bug -> [1]
Missed bug:
```python
def common(l1: list, l2: list):
    l1 = list(set(l1))
    l2 = list(set(l2))
    sorted_l1 = sorted(l1)
    sorted_l2 = sorted(l2)
    return list(filter(lambda x: x in sorted_l2, sorted_l1))
```
Exposing input: ([False, None], [])  reference -> []  bug -> <exc TypeError>

### HumanEval/64: Add more test cases.
Inputs tried: ('',); ('y',); ('by',); ('yes',); ('AEIOUY',)
Bugs exposed: 3 of 4
Missed bug:
```python
FIX = '\nAdd more test cases.\n'

def vowels_count(s):
    count = 0
    vowels = 'aeiouy'
    for i in s:
        if i.lower() in vowels:
            if i.lower() == 'y' and s.index(i) != len(s) - 1:
                continue
            count += 1
    return count
```
Exposing input: ('yy',)  reference -> 1  bug -> 0

### HumanEval/76: Your task is to write a function that returns true if a number x is a simple power of n and false in other cases. x is a simple power of n if n**int=x For example: is_simple_power(1, 4) => true is_simple_power(2, 2) => true is_simple_power(
Inputs tried: (1, 1); (-8, -2); (8, -2); (0, 2); (2, 0)
Bugs exposed: 17 of 18
Missed bug:
```python
def is_simple_power(x, n):
    for i in range(10000):
        if x == n ** i:
            return True
    return False
```
Exposing input: (7, 15)  reference -> False  bug -> False

### HumanEval/87: You are given a 2 dimensional data, as a nested lists, which is similar to matrix, however, unlike matrices, each row may contain a different number of columns. Given lst, and integer x, find integers x in the list, and return list of tuple
Inputs tried: ([[0, 1, 0, 2, 0], [3, 4], [0]], 0); ([[-5, -5, 0, -5], [1, -5, 2], [], [-5]], -5); ([[1, 2, 3], [4, 5], [6]], 9); ([[], [], []], 1); ([[0, 0, 0, 0, 0, 0, 0, 0, 0, 7, 7, 0, 7], [7, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 7], [1, 2, 3]], 7)
Bugs exposed: 2 of 2

### HumanEval/89: Create a function encrypt that takes a string as an argument and returns a string encrypted with the alphabet being rotated. The alphabet should be rotated in a manner such that the letters shift down by two multiplied to two places. For ex
Inputs tried: ('',); ('z',); ('xyz',); ('abcdefghijklmnopqrstuvwxyz',); ('a b1z',)
Bugs exposed: 4 of 4

### HumanEval/95: Given a dictionary, return True if all keys are strings in lower case or all keys are strings in upper case, else return False. The function should return False is the given dictionary is empty. Examples: check_dict_case({"a":"apple", "b":"
Inputs tried: ({},); ({'123': 'x', '456': 'y'},); ({'a': 'x', '_': 'y'},); ({'A': 'x', '1': 'y'},); ({'': 'x'},)
Bugs exposed: 0 of 2
Missed bug:
```python
def check_dict_case(dict):
    if dict:
        if all([k.isalpha() for k in dict.keys()]) and all([k.isupper() for k in dict.keys()]):
            return True
        elif all([k.isalpha() for k in dict.keys()]) and all([k.islower() for k in dict.keys()]):
            return True
        else:
            return False
    else:
        return False
```
Exposing input: ({'or$50,00ange': 'fruui'},)  reference -> True  bug -> False
Missed bug:
```python
def check_dict_case(dict):
    if len(dict) == 0:
        return False
    if all((isinstance(dict[key], str) for key in dict.keys())):
        if all((key.islower() for key in dict.keys())):
            return True
        elif all((key.isupper() for key in dict.keys())):
            return True
        else:
            return False
    else:
        return False
```
Exposing input: ({'PI': 3.14159},)  reference -> True  bug -> False

### HumanEval/97: Complete the function that takes two integers and returns the product of their unit digits. Assume the input is always valid. Examples: multiply(148, 412) should return 16. multiply(19, 28) should return 72. multiply(2020, 1851) should retu
Inputs tried: (-19, 7); (7, -19); (-28, -37); (-123456789, 4); (-10, 3)
Bugs exposed: 2 of 2

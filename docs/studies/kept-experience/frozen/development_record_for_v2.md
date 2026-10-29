Experience from earlier testing sessions on other functions. For each, you see the inputs that were tried, then each hidden bug that those inputs MISSED, with the buggy code and an input that exposes it.

### HumanEval/0: Check if in given list of numbers, are any two numbers closer to each other than given threshold. >>> has_close_elements([1.0, 2.0, 3.0], 0.5) False >>> has_close_elements([1.0, 2.8, 3.0, 4.0, 5.0, 2.0], 0.3) True
Inputs tried: ([1.0, 10.0, 1.4], 0.5); ([0.0, 1.0], 1.0); ([10.0, 1.0], 5.0); ([2.0], 0.5); ([-5.0, -100.0, -5.0], 0.0001)
Bugs exposed: 5 of 6
Missed bug:
```python
from typing import List

def has_close_elements(numbers: List[float], threshold: float) -> bool:
    numbers_sorted = sorted(numbers)
    closest_nr = numbers_sorted[0]
    for n in numbers_sorted[1:]:
        if abs(n - closest_nr) < threshold:
            return True
        else:
            closest_nr = n
    return False
```
Exposing input: ([], 0.5)  reference -> False  bug -> <exc IndexError>

### HumanEval/10: Test if given string is a palindrome
Inputs tried: ('abba',); ('abb',); ('abc',); ('abab',); ('aab',)
Bugs exposed: 2 of 2

### HumanEval/102: This function takes two positive numbers x and y and returns the biggest even integer number that is in the range [x, y] inclusive. If there's no such number, then the function should return -1. For example: choose_num(12, 15) = 14 choose_n
Inputs tried: (3, 2); (2, 2); (1, 1); (1, 2); (4, 5)
Bugs exposed: 0 of 1
Missed bug:
```python
def choose_num(x, y):
    if x % 2 == 0 and x <= y:
        biggest_even = x
    elif y % 2 == 0 and y >= x:
        biggest_even = y
    else:
        return -1
    for i in range(biggest_even, y + 1, 2):
        if i % 2 == 0:
            biggest_even = i
    return biggest_even
```
Exposing input: (3, 5)  reference -> 4  bug -> -1

### HumanEval/110: In this problem, you will implement a function that takes two lists of numbers, and determines whether it is possible to perform an exchange of elements between them to make lst1 a list of only even numbers. There is no limit on the number 
Inputs tried: ([2, 4, 6], [1, 3, 5]); ([1, 3], [2, 4]); ([1, 3, 5], [2, 4]); ([1, 3, 5], [1, 3, 5, 7]); ([-1, 0, -2], [-4, -3])
Bugs exposed: 2 of 3
Missed bug:
```python
def exchange(lst1, lst2):
    even_lst1 = [num for num in lst1 if num % 2 == 0]
    odd_lst1 = [num for num in lst1 if num % 2 != 0]
    even_lst2 = [num for num in lst2 if num % 2 == 0]
    odd_lst2 = [num for num in lst2 if num % 2 != 0]
    if len(odd_lst1) > len(even_lst2) or len(odd_lst2) > len(even_lst1):
        return 'NO'
    return 'YES'
```
Exposing input: ([6], [1, 7, 7])  reference -> 'YES'  bug -> 'NO'

### HumanEval/117: Given a string s and a natural number n, you have been tasked to implement a function that returns a list of all words from string s that contain exactly n consonants, in order these words appear in the string s. If the string s is empty th
Inputs tried: ('', 0); ('  a cat  e  ', 0); ('cat cat', 2); ('quick', 3); ('café', 3)
Bugs exposed: 3 of 3

### HumanEval/12: Out of list of strings, return the longest one. Return the first one in case of multiple strings of the same length. Return None in case the input list is empty. >>> longest([]) >>> longest(['a', 'b', 'c']) 'a' >>> longest(['a', 'bb', 'ccc'
Inputs tried: ([],); ([''],); (['   ', 'a'],); (['a', 'bb', 'cc'],); (['', 'a', 'bb', 'cc'],)
Bugs exposed: 1 of 1

### HumanEval/124: You have to write a function which validates a given date string and returns True if the date is valid otherwise False. The date is valid if all of the following rules are satisfied: 1. The date string is not empty. 2. The number of days is
Inputs tried: ('02-29-2021',); ('02-30-2020',); ('04-31-2020',); ('01-31-2020',); ('4-05-2020',)
Bugs exposed: 45 of 51
Missed bug:
```python
def valid_date(date):
    if len(date) != 10:
        return False
    month, day, year = date.split('-')
    try:
        month = int(month)
        day = int(day)
        year = int(year)
    except ValueError:
        return False
    if month < 1 or month > 12:
        return False
    if month in [4, 6, 9, 11] and (day < 1 or day > 30):
        return False
    elif month == 2 and (day < 1 or day > 29):
        return False
    elif day < 1 or day > 31:
        return False
    return True
```
Exposing input: ('06/04/2020',)  reference -> False  bug -> <exc ValueError>
Missed bug:
```python
def valid_date(date):
    if not date:
        return False
    if len(date) != 10 or date[2] != '-' or date[5] != '-':
        return False
    month, day, year = (date[:2], date[3:5], date[6:])
    if not month.isdigit() or not 1 <= int(month) <= 12:
        return False
    if month in ['01', '03', '05', '07', '08', '10', '12']:
        if not day.isdigit() or not 1 <= int(day) <= 31:
            return False
    elif month in ['04', '06', '09', '11']:
        if not day.isdigit() or not 1 <= int(day) <= 30:
            return False
    elif month == '02':
        if not day.isdigit() or not 1 <= int(day) <= 29:
            return False
    return True
```
Exposing input: ('04-02-2-20',)  reference -> False  bug -> True
Missed bug:
```python
def valid_date(date):
    if not date:
        return False
    try:
        month, day, year = date.split('-')
    except ValueError:
        return False
    month_days = {'01': 31, '02': 29, '03': 31, '04': 30, '05': 31, '06': 30, '07': 31, '08': 31, '09': 30, '10': 31, '11': 30, '12': 31}
    if month not in month_days.keys():
        return False
    if not 1 <= int(day) <= month_days[month]:
        return False
    if not 1 <= int(month) <= 12:
        return False
    return True
```
Exposing input: ('01-2-020',)  reference -> False  bug -> True

### HumanEval/13: Return a greatest common divisor of two integers a and b >>> greatest_common_divisor(3, 5) 1 >>> greatest_common_divisor(25, 15) 5
Inputs tried: (1, 1); (3, 6); (6, 3); (12, 18); (701408733, 433494437)
Bugs exposed: 2 of 4
Missed bug:
```python
def greatest_common_divisor(a: int, b: int) -> int:
    while a != b:
        if a > b:
            a = a - b
        else:
            b = b - a
    return a
```
Exposing input: (987654320, 987654321)  reference -> 1  bug -> <timeout>
Missed bug:
```python
def greatest_common_divisor(a: int, b: int) -> int:
    if a == 0:
        return b
    elif b == 0:
        return a
    elif a == b:
        return a
    elif a > b:
        return greatest_common_divisor(a - b, b)
    else:
        return greatest_common_divisor(a, b - a)
```
Exposing input: (10, 3699636)  reference -> 2  bug -> <exc RecursionError>

### HumanEval/140: Given a string text, replace all spaces in it with underscores, and if a string has more than 2 consecutive spaces, then replace all consecutive spaces with - fix_spaces("Example") == "Example" fix_spaces("Example 1") == "Example_1" fix_spa
Inputs tried: ('a___b',); ('a  b',); ('a  b   c    d',); ('a   ',); ('   ',)
Bugs exposed: 3 of 4
Missed bug:
```python
def fix_spaces(text):
    result = ''
    consecutive_spaces = 0
    for i in range(len(text)):
        if text[i] == ' ':
            if consecutive_spaces == 2:
                result = result[:-2] + '-'
            elif consecutive_spaces > 2:
                pass
            else:
                result += '_'
            consecutive_spaces += 1
        else:
            result += text[i]
            consecutive_spaces = 0
    if consecutive_spaces == 2:
        result = result[:-2] + '-'
    return result
```
Exposing input: ('  ',)  reference -> '__'  bug -> '-'

### HumanEval/147: You are given a positive integer n. You have to create an integer array a of length n. For each i (1 ≤ i ≤ n), the value of a[i] = i * i - i + 1. Return the number of triples (a[i], a[j], a[k]) of a where i < j < k, and a[i] + a[j] + a[k] i
Inputs tried: (1,); (4,); (8,); (11,); (1000000,)
Bugs exposed: 1 of 1

### HumanEval/150: A simple program which should return the value of x if n is a prime number and should return the value of y otherwise. Examples: for x_or_y(7, 34, 12) == 34 for x_or_y(15, 8, 5) == 5
Inputs tried: (1, 1001, 2002); (2, 1003, 2004); (9, 1005, 2006); (-7, 1007, 2008); (7919, 1009, 2010)
Bugs exposed: 5 of 5

### HumanEval/152: I think we all remember that feeling when the result of some long-awaited event is finally known. The feelings and thoughts you have at that moment are definitely worth noting down and comparing. Your task is to determine if a person correc
Inputs tried: ([], []); ([-7], [3]); ([5, -2, 0, -9], [5, 3, 4, -1]); ([2, 2, 2, 2, 2], [1, 3, -1, 2, 0]); ([1000000000000000000, -1000000000000000000, 123456789, -123456789], [-1000000000000000000, 1000000000000000000, -123456789, 123456789])
Bugs exposed: 2 of 2

### HumanEval/27: For a given string, flip lowercase characters to uppercase and uppercase to lowercase. >>> flip_case('Hello') 'hELLO'
Inputs tried: ('',); ('aaaAAA000!!!',); ('äÄöÖüÜß',); ('ǅǆǄİıΣσς',); ('A',)
Bugs exposed: 3 of 3

### HumanEval/34: Return sorted unique elements in a list >>> unique([5, 3, 5, 2, 3, 3, 9, 0, 123]) [0, 2, 3, 5, 9, 123]
Inputs tried: ([],); ([5, 5, 5, 5],); ([0, 1, -1, 1, 0, -2, 3, -1],); (['', 'b', 'a', 'b', '', 'c'],); ([True, False, 2, 0, True, 1],)
Bugs exposed: 3 of 4
Missed bug:
```python
def unique(l: list):
    if not l:
        return []
    l.sort()
    unique_list = []
    for i in l:
        if i not in unique_list:
            unique_list.append(i)
    return unique_list
```
Exposing input: ([None, None, None, None],)  reference -> [None]  bug -> <exc TypeError>

### HumanEval/4: For a given list of input numbers, calculate Mean Absolute Deviation around the mean of this dataset. Mean Absolute Deviation is the average absolute difference between each element and a centerpoint (mean in this case): MAD = average | x -
Inputs tried: (1.0,); ([0.0, 0.0, 0.0, 10.0],); ([1.0, 2.0, 3.0, 10.0],); ([-5.0, -1.0, 0.0, 2.0],); ([0.0, 1.0, 2.0],)
Bugs exposed: 2 of 3
Missed bug:
```python
from typing import List

def mean_absolute_deviation(numbers: List[float]) -> float:
    n = len(numbers)
    if n < 2:
        raise ValueError('MAD requires at least two data points')
    mean = sum(numbers) / n
    absolute_deviations = [abs(x - mean) for x in numbers]
    return sum(absolute_deviations) / n
```
Exposing input: ([1.0],)  reference -> 0.0  bug -> <exc ValueError>

### HumanEval/41: Imagine a road that's a perfectly straight infinitely long line. n cars are driving left to right; simultaneously, a different set of n cars are driving right to left. The two sets of cars start out being very far from each other. All cars 
Inputs tried: (1,); (2,); (3,); (10,); (1000000000,)
Bugs exposed: 1 of 1

### HumanEval/43: pairs_sum_to_zero takes a list of integers as an input. it returns True if there are two distinct elements in the list that sum to zero, and False otherwise. >>> pairs_sum_to_zero([1, 3, 5, 0]) False >>> pairs_sum_to_zero([1, 3, -2, 1]) Fal
Inputs tried: ([],); ([0],); ([0, 0],); ([1, 2, -3],); ([3, 3, 3],)
Bugs exposed: 8 of 11
Missed bug:
```python
def pairs_sum_to_zero(l):
    l.sort()
    i = 0
    j = len(l) - 1
    while i < j:
        if l[i] + l[j] == 0:
            return True
        elif l[i] + l[j] > 0:
            j -= 1
        else:
            i += 1
    return False
```
Exposing input: ('',)  reference -> False  bug -> <exc AttributeError>
Missed bug:
```python
def pairs_sum_to_zero(l):
    for i in range(len(l) - 1):
        for j in range(i, len(l)):
            if l[i] + l[j] == 0:
                return True
    return False
```
Exposing input: ([0, 1],)  reference -> False  bug -> True
Missed bug:
```python
def pairs_sum_to_zero(l):
    if len(l) < 2:
        return False
    for i in l[:-1]:
        for j in l[1:]:
            if i == -j:
                return True
    return False
```
Exposing input: ([-2, 0, -4],)  reference -> False  bug -> True

### HumanEval/51: remove_vowels is a function that takes string and returns string without vowels. >>> remove_vowels('') '' >>> remove_vowels("abcdef\nghijklm") 'bcdf\nghjklm' >>> remove_vowels('abcdef') 'bcdf' >>> remove_vowels('aaaaa') '' >>> remove_vowels
Inputs tried: ('AEIOUaeiou',); ('bcdfghjklmnpqrstvwxyz',); ('This Is A Test',); ('a1e2i3o4u5!?',); ('éàü',)
Bugs exposed: 3 of 3

### HumanEval/56: brackets is a string of "<" and ">". return True if every opening bracket has a corresponding closing bracket. >>> correct_bracketing("<") False >>> correct_bracketing("<>") True >>> correct_bracketing("<<><>>") True >>> correct_bracketing(
Inputs tried: ('',); ('>',); ('<>>',); ('<>><<>',); ('<><>',)
Bugs exposed: 1 of 1

### HumanEval/61: brackets is a string of "(" and ")". return True if every opening bracket has a corresponding closing bracket. >>> correct_bracketing("(") False >>> correct_bracketing("()") True >>> correct_bracketing("(()())") True >>> correct_bracketing(
Inputs tried: ('',); (')(',); ('())(',); ('())(()',); ('()()()()()()()()()()()()()()()()()()()()',)
Bugs exposed: 1 of 1

### HumanEval/68: "Given an array representing a branch of a tree that has non-negative integer nodes your task is to pluck one of the nodes and return it. The plucked node should be the node with the smallest even value. If multiple nodes with the same smal
Inputs tried: ([2, 4, 6],); ([1, 3, 5],); ([6, 4, 4, 8],); ([3, 5, 4],); ([1, 1, 1, 1, 1, 1, 1, 1, 1, 2],)
Bugs exposed: 0 of 2
Missed bug:
```python
def pluck(arr):
    if len(arr) == 0:
        return []
    index = None
    min_ = 9999
    for idx, num in enumerate(arr):
        if 0 == num % 2:
            if num < min_:
                index = idx
                min_ = num
    return [min_, index] if index is not None else []
```
Exposing input: ([1, 25, 10000, 25],)  reference -> [10000, 2]  bug -> []
Missed bug:
```python
def pluck(arr):
    if len(arr) == 0:
        return []
    elif len(arr) == 1:
        return [arr[0], 0]
    even = []
    min_even = None
    i = None
    for num in arr:
        if num % 2 == 0:
            even.append(num)
            if min_even == None:
                min_even = num
            elif num < min_even:
                min_even = num
    if len(even) > 0:
        i = arr.index(min_even)
        return [min_even, i]
    else:
        return []
```
Exposing input: ([3],)  reference -> []  bug -> [3, 0]

### HumanEval/69: You are given a non-empty list of positive integers. Return the greatest integer that is greater than zero, and has a frequency greater than or equal to the value of the integer itself. The frequency of an integer is the number of times it 
Inputs tried: ([1],); ([2],); ([1, 1, 2],); ([3, 3, 3, 3, 2, 2, 1, 1],); ([4, 4, 4, 4],)
Bugs exposed: 0 of 1
Missed bug:
```python
def search(lst):
    frequency_dict = {}
    for num in set(lst):
        frequency_dict[num] = lst.count(num)
    result = -1
    for num, freq in frequency_dict.items():
        if num <= freq > result:
            result = num
    return result
```
Exposing input: ([1, 1, 11, 1, 1, 1, 1, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 3],)  reference -> 3  bug -> 2

### HumanEval/75: Write a function that returns true if the given number is the multiplication of 3 prime numbers and false otherwise. Knowing that (a) is less then 100. Example: is_multiply_prime(30) == True 30 = 2 * 3 * 5
Inputs tried: (8,); (12,); (99,); (16,); (6,)
Bugs exposed: 6 of 9
Missed bug:
```python
def is_multiply_prime(a):
    primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79, 83, 89, 97]
    factors = []
    for p in primes:
        while a % p == 0:
            factors.append(p)
            a = a // p
        if a == 1:
            break
    return len(factors) == 3
```
Exposing input: (0,)  reference -> False  bug -> <timeout>
Missed bug:
```python
def is_multiply_prime(a):
    primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79, 83, 89, 97]
    factors = []
    for p in primes:
        while a % p == 0:
            a //= p
            factors.append(p)
        if a == 1 or p > a:
            break
    return a == 1 and len(factors) == 3
```
Exposing input: (0,)  reference -> False  bug -> <timeout>
Missed bug:
```python
def is_multiply_prime(a):
    count = 0
    while a % 2 == 0:
        count += 1
        a //= 2
    i = 3
    while i * i <= a and count < 3:
        while a % i == 0:
            count += 1
            a //= i
        i += 2
    if a > 1:
        count += 1
    return count == 3
```
Exposing input: (0,)  reference -> False  bug -> <timeout>

### HumanEval/78: You have been tasked to write a function that receives a hexadecimal number as a string and counts the number of hexadecimal digits that are primes (prime number, or a prime, is a natural number greater than 1 that is not a product of two s
Inputs tried: ('',); ('B',); ('0',); ('0123456789ABCDEF',); ('22222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222
Bugs exposed: 0 of 1
Missed bug:
```python
def hex_key(num):
    return num.count('2') + num.count('3') + num.count('5') + num.count('7') + num.count('B') + num.count('D')
```
Exposing input: ({},)  reference -> 0  bug -> <exc AttributeError>

### HumanEval/8: For a given list of integers, return a tuple consisting of a sum and a product of all the integers in a list. Empty sum should be equal to 0 and empty product should be equal to 1. >>> sum_product([]) (0, 1) >>> sum_product([1, 2, 3, 4]) (1
Inputs tried: ([5],); ([2, 3],); ([0, 2, 3],); ([-1, 2, -3],); ([2, 2, 2],)
Bugs exposed: 0 of 4
Missed bug:
```python
from typing import List, Tuple

def sum_product(numbers: List[int]) -> Tuple[int, int]:
    if not numbers:
        return (0, 1)
    sum_ = numbers[0]
    product = numbers[0]
    for num in numbers[1:]:
        sum_ += num
        product *= num
    return (sum_, product)
```
Exposing input: ([True],)  reference -> (1, 1)  bug -> (True, True)
Missed bug:
```python
from typing import List, Tuple

def sum_product(numbers: List[int]) -> Tuple[int, int]:
    if not isinstance(numbers, list):
        raise ValueError('Only list of integers are allowed')
    elif all((isinstance(i, int) for i in numbers)):
        sum_, prod = (0, 1)
        for num in numbers:
            sum_ += num
            prod *= num
        return (sum_, prod)
    else:
        raise ValueError('Only list of integers are allowed')
```
Exposing input: ('',)  reference -> (0, 1)  bug -> <exc ValueError>
Missed bug:
```python
from typing import List, Tuple

def sum_product(numbers: List[int]) -> Tuple[int, int]:
    len_numbers = len(numbers)
    if len_numbers == 0:
        return (0, 1)
    elif len_numbers == 1:
        return (numbers[0], numbers[0])
    else:
        return (numbers[0] + sum_product(numbers[1:])[0], numbers[0] * sum_product(numbers[1:])[1])
```
Exposing input: ([1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],)  reference -> (57, 1)  bug -> <timeout>

### HumanEval/80: You are given a string s. Your task is to check if the string is happy or not. A string is happy if its length is at least 3 and every 3 consecutive letters are distinct For example: is_happy(a) => False is_happy(aa) => False is_happy(abcd)
Inputs tried: ('aba',); ('abca',); ('abcbd',); ('aaa',); ('a!A',)
Bugs exposed: 2 of 2

### HumanEval/86: Write a function that takes a string and returns an ordered version of it. Ordered version of string, is a string where all words (separated by space) are replaced by a new word where all the characters arranged in ascending order based on 
Inputs tried: ('',); ('   ',); (' aB  b!a ',); ('b2A c1B',); ('a!A !a',)
Bugs exposed: 3 of 3

### HumanEval/98: Given a string s, count the number of uppercase vowels in even indices. For example: count_upper('aBCdEf') returns 1 count_upper('abcdefg') returns 0 count_upper('dBBE') returns 0
Inputs tried: ('',); ('A',); ('YEAbIcUdOea',); ('AEIOU',); ('AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',)
Bugs exposed: 1 of 1

### HumanEval/99: Create a function that takes a value (string) representing a number and returns the closest integer to it. If the number is equidistant from two integers, round it away from zero. Examples >>> closest_integer("10") 10 >>> closest_integer("1
Inputs tried: ('14.5',); ('-14.5',); ('15.7',); ('-15.3',); ('-0.5',)
Bugs exposed: 5 of 6
Missed bug:
```python
def closest_integer(value):
    if '.' not in value:
        return int(value)
    else:
        num = float(value)
        if num > 0:
            if num - int(num) >= 0.5:
                return int(num) + 1
            else:
                return int(num)
        elif num - int(num) <= -0.5:
            return int(num) - 1
        else:
            return int(num)
```
Exposing input: ('3456789000000000001',)  reference -> 3456789000000000000  bug -> 3456789000000000001
